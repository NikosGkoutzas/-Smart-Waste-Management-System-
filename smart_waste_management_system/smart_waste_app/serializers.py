from rest_framework import serializers
from .models import *
from django.utils import timezone
from datetime import timedelta , date
from dateutil.relativedelta import relativedelta




class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True , required=False)
    username = serializers.CharField(read_only=True)
    organizations = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id' , 'first_name' , 'last_name' , 'username' , 'password' , 'organizations' , 'role']
    


    def validate(self , data):
        first_name = data.get('first_name')
        last_name = data.get('last_name')

        if(not first_name.isalpha()):
            raise serializers.ValidationError('First name must contain only letters.')


        if(not last_name.isalpha()):
            raise serializers.ValidationError('Last name must contain only letters.')

        return data


    def create(self , validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user



    def get_organizations(self , obj):
        user_organizations = obj.organizations.all()
        if(user_organizations):
            return ' , '.join([(str(org.name) + str(' (') + str(org.location) + str(')')) for org in user_organizations])
        return '-'





class OrganizationSerializer(serializers.ModelSerializer):
    users = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Organization
        fields = ['id' , 'name' , 'location' , 'contact_email' , 'organization_type' , 'established_date' , 'users']

    
    def get_users(self , obj):
        users = []
        for user in obj.users.all(): # Here is the inverse relationship between CustomUser and Organization models (user -> manytomanyfield to org.)
            users.append(user.first_name + ' ' + user.last_name + ' (' + user.role + ')')
        return ' , '.join(users)


    def validate(self , data):
        name = data.get('name')
        est_date = data.get('established_date')

        if(not name.isalpha()):
            raise serializers.ValidationError('Organization name must contain only letters.')

        if(est_date > date.today()):
            raise serializers.ValidationError('Established date cannot exceed the current date')
        return data






class BinSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Bin
        fields = ['id' , 'organization' , 'location' , 'bin_type' , 'capacity' , 'current_fill_level' , 'status']


    def get_organization(self, obj):
        return obj.organization.name


    def __init__(self , *args , **kwargs):
        super().__init__(*args , **kwargs)
        org_id = self.context.get('organization_pk')
        if(org_id):
            town = Organization.objects.filter(id=org_id).first()
            if(town):
                location = town.location
                self.fields['location'].help_text = f'Provide an address in {location}. eg: (Address), {location}'


    def validate(self , data):
        current_fill_level = data.get('current_fill_level')
        capacity = data.get('capacity')

        if(current_fill_level > capacity):
            raise serializers.ValidationError('Current fill level must not exceed bin capacity.')
        return data







class TruckSerializer(serializers.ModelSerializer):
    license_plate = serializers.CharField(read_only=True)
    current_load = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    speed = serializers.IntegerField(read_only=True)
    organization = serializers.SerializerMethodField(read_only=True)
    location = serializers.CharField(required=True)


    class Meta:
        model = Truck
        fields = ['id' , 'organization' , 'license_plate' , 'location' , 'capacity' , 'current_load' , 'speed_category' , 'speed' , 'status' , 'unload']


    def get_organization(self , obj):
        return obj.organization.name
    

    def __init__(self , *args , **kwargs):
        super().__init__(*args , **kwargs)
        org_id = self.context.get('organization_pk')
        
        if(org_id):
            town = Organization.objects.filter(id=org_id).first()
            if(town):
                location = town.location
                self.fields['location'].help_text = f'Provide an address in {location}. eg: (Address), {location}'


    def to_representation(self , instance):
        rep = super().to_representation(instance)
        rep['current_load'] = f'{instance.current_load:.1f}'
        return rep












class PickUpRequestSerializer(serializers.ModelSerializer):
    requested_by = serializers.SerializerMethodField(read_only=True)
    expected_weight = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    distance = serializers.SerializerMethodField(read_only=True)
    expected_time = serializers.SerializerMethodField(read_only=True)
    route = serializers.SerializerMethodField(read_only=True)
    truck_speed = serializers.SerializerMethodField(read_only=True)
    requested_at = serializers.SerializerMethodField(read_only=True)
    pickup_at = serializers.SerializerMethodField(read_only=True)
    current_load = serializers.SerializerMethodField(read_only=True)
    warnings = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PickUpRequest
        fields = ['id' , 'auto_assign_all' , 'bin' , 'expected_weight' , 'truck' , 'current_load' , 'auto_assign_truck' , 'requested_by' , 'status' , \
                  'scheduled_at' , 'now' , 'distance' , 'expected_time' , 'truck_speed' , 'route' , 'requested_at' , 'pickup_at' , 'warnings']


    def get_requested_by(self , obj):
        if(obj.requested_by.name):
            return obj.requested_by.name
        return None
    

    def get_current_load(self , obj):
        if(obj.truck):
            return obj.truck.current_load
        return None
    

    def get_requested_at(self , obj):
        if(obj.requested_at):
            return (obj.requested_at + timedelta(hours=3)).strftime("%d/%m/%Y, %H:%M:%S")
        return None


    def get_pickup_at(self , obj):
        if(obj.pickup_at):
            return obj.pickup_at.strftime("%d/%m/%Y, %H:%M:%S")
        return None


    def get_expected_weight(self , obj):
        pickup_request = PickUpRequest.objects.filter(id = self.context.get('pickup_request_pk'))

        if(not obj.bin):
            return
        
        elif(not pickup_request.first()):
            return obj.bin.current_fill_level

        return sum(p.bin.current_fill_level for p in pickup_request) / len(pickup_request)        



    def get_distance(self , obj):
        return obj.distance
    


    def get_expected_time(self , obj):
        return obj.expected_time
    


    def get_route(self , obj):
        if(obj.truck and obj.bin):
            return f'{obj.truck.location}  ->  {obj.bin.location}'



    def get_truck_speed(self , obj):
        if(obj.truck):
            return obj.truck.speed



    def get_warnings(self , obj):
        return f'⚠️ {obj.warnings}'


    def validate(self , data):
        now = data.get('now')
        bin = data.get('bin')
        truck = data.get('truck')
        scheduled_at = data.get('scheduled_at')
        auto_assign_truck = data.get('auto_assign_truck')
        auto_assign_all = data.get('auto_assign_all')

        if(not bin and not auto_assign_all):
            raise serializers.ValidationError(f'Bin must be selected!')
        
        if(not truck and not auto_assign_truck and not auto_assign_all):
            raise serializers.ValidationError(f'Truck must be selected!')

        if(now):
            data['scheduled_at'] = None
        
        if(auto_assign_all):
            auto_assign_truck = False

        if(not now):
            if(not scheduled_at):
                raise serializers.ValidationError('Pickup time is required. Please select either \'Now\' or a scheduled date and time.')
            
            if(scheduled_at < timezone.now() + timedelta(hours=3)):
                raise serializers.ValidationError('\'Scheduled at\' time must be set to a future time.')
            
        return data
    


    def to_representation(self , instance):
        rep = super().to_representation(instance)

        truck_ = instance.truck
        bin_ = instance.bin
        distance = instance.distance

        if(not truck_ or not bin_):
            # 8a balw kai alla pedia kai 8a kanw assign ta pragmatika otan ginontai create se auta ta temporary 
            rep['warnings'] = '❌ Pickup request has been deleted.'
            

        else:
            if(truck_ and bin_ and instance.truck.location and instance.bin.location):
                if(distance == -1):
                    rep['distance'] = 'Calculating... Please refresh.'
                    rep['expected_time'] = 'Calculating... Please refresh.'
                    rep['pickup_at'] = 'Calculating... Please refresh.'
                else:
                    rep['distance'] = f'{self.get_distance(instance):.1f} meters'
                    rep['expected_time'] = f'{self.get_expected_time(instance):.1f} seconds'
                    rep['pickup_at'] = self.get_pickup_at(instance)

            rep['requested_at'] = self.get_requested_at(instance)
            rep['truck_speed'] = f'{self.get_truck_speed(instance)} Km/h'

            if(truck_ and bin_):
                rep['truck'] = f'{truck_.license_plate}'
                rep['bin'] = f'{bin_.bin_type} / {bin_.location}'

            if(instance.now):
                rep['scheduled_at'] = None


            if(not instance.auto_assign_truck or instance.auto_assign_all):
                rep.pop('auto_assign_truck')

            if(not instance.now):
                rep.pop('now')

            if(not instance.warnings):
                rep.pop('warnings')
            
            rep.pop('scheduled_at')
            
        return rep






class CollectionSerializer(serializers.ModelSerializer):
    pickup_request = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Collection
        fields = ['id' , 'pickup_request' , 'collected_weight' , 'collected_at' , 'status']
        read_only_fields = fields   # all varaibles are for read only. No post, no updates, only GET. All automatically. 

    def get_pickup_request(self , obj):
        return obj.pickup_request.id + '. ' + obj.pickup_request.truck + ' -> ' + obj.pickup_request.bin