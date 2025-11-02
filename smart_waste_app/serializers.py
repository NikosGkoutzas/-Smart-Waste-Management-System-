from rest_framework import serializers , status
from rest_framework.exceptions import ValidationError
from .models import *
from django.db.models import Q
from datetime import date




class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True , required=False)
    username = serializers.CharField()
    organization = serializers.SerializerMethodField()
    registered_on = serializers.SerializerMethodField()
    notifications = serializers.CharField(read_only=True)
    request_to_join = serializers.SerializerMethodField()
    admin_successor = serializers.SerializerMethodField()
    
    

    class Meta:
        model = CustomUser
        fields = ['id' , 'first_name' , 'last_name' , 'username' , 'password' , 'organization' , 'available_for_work' , 'role' , \
                  'registered_on' , 'request_to_join' , 'admin_successor' , 'sumbit_resignation' , 'notifications']
    

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        user_id = self.context.get('id')
        admin_user = CustomUser.objects.filter(id = user_id , role = 'Admin').first()
        current_user = CustomUser.objects.filter(id=user_id).first()
        
        if(user_id):
            if(request and request.method in ['PUT' , 'PATCH']):
                fields['first_name'].read_only = True
                fields['last_name'].read_only = True


        if(request and request.method == 'POST'):
            fields.pop('username' , None)
            fields.pop('sumbit_resignation' , None)


        if(admin_user):
            fields.pop('available_for_work' , None)
            fields.pop('sumbit_resignation' , None)
            fields.pop('request_to_join' , None)

            if(admin_user.organization):
                fields['role'].read_only = True  
            
            if(admin_user.organization):
                invited_admins = CustomUser.objects.exclude(Q(id__in=Invitation.objects.filter(status='Pending' , reason='admin_successor') 
                                                    .filter(sender_user=user_id)
                                                    .values_list('receiver_user__id' , flat=True))).exclude(id=user_id) \
                                                    .filter(organization = admin_user.organization) \
                                                    .exclude(Q(id__in=Reply.objects.filter(final_decision='Pending' , receiver_user=user_id)
                                                    .values_list('invitation__receiver_user__id' , flat=True))).exclude(id=user_id)                
                
                if(CustomUser.objects.exclude(id=user_id).filter(organization = admin_user.organization).exists() and invited_admins.exists()):
                    fields['admin_successor'] = serializers.PrimaryKeyRelatedField(queryset = invited_admins , required=False , allow_null=True)
                else:
                    fields.pop('admin_successor' , None)

        else:
            if(current_user):
                if(current_user.sumbit_resignation):
                    fields['sumbit_resignation'].read_only = True

                if(current_user.organization):
                    fields.pop('available_for_work' , None)
                    fields['role'].read_only = True                

                else:
                    fields.pop('sumbit_resignation' , None)

                orgIsHiring = Organization.objects.filter(hiring = True).exclude(members=current_user).exclude(
                                                    Q(id__in = Invitation.objects.filter(Q(sender_user=current_user) , status='Pending').values_list('receiver_organization__id' , flat=True)) 
                                                  | Q(id__in = Invitation.objects.filter(Q(receiver_user=current_user) , status='Pending').values_list('sender_organization__id' , flat=True))
                                                  | Q(id__in = Reply.objects.filter(receiver_user=current_user , final_decision = 'Pending').values_list('invitation__receiver_organization__id' , flat=True)))

                if(not orgIsHiring.exists() or not Organization.objects.exists() ):
                    fields.pop('request_to_join' , None)

                else:
                    fields['request_to_join'] = serializers.PrimaryKeyRelatedField(many=True , queryset = orgIsHiring , required=False)


        return fields
    



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
        request_to_join = validated_data.pop('request_to_join', [])  # because it's ManyToManyField field
        
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        user.request_to_join.set(request_to_join)
        return user



    def get_organization(self , obj):
        if(obj.organization):
            return obj.organization.name
        return None



    def get_registered_on(self , obj):
        local_time = timezone.localtime(obj.registered_on)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")


    def get_request_to_join(self , obj):
        if(obj.request_to_join):
            return obj.request_to_join.name
        return None
    


    def get_admin_successor(self , obj):
        if(obj.admin_successor):
            return obj.admin_successor
        return None
    


    def to_representation(self , instance):        
        if(instance):
            invitations = Invitation.objects.filter(receiver_user = instance , status='Pending')
            replies = Reply.objects.filter(receiver_user = instance , final_decision='Pending')

            if(invitations.exists()):
                last_invitation = invitations.last().receiver_user_notification
            
                if(instance.receiver_user_invitations.filter(status = 'Pending').count() == 1):
                    instance.notifications = f'{last_invitation} Check out your received-invitations.'
                elif(instance.receiver_user_invitations.filter(status = 'Pending').count() > 1):
                    instance.notifications = f'{last_invitation} Also, you have {instance.receiver_user_invitations.filter(status = 'Pending').count()-1} more notifications. Check out your received-invitations.'
            
            if(replies.exists()):
                last_reply = replies.last().receiver_user_notification

                if(instance.receiver_user_replies.filter(final_decision = 'Pending').count() == 1):
                    instance.notifications = f'{last_reply} Check out your replies.'
                elif(instance.receiver_user_replies.filter(final_decision = 'Pending').count() > 1):
                    instance.notifications = f'{last_reply} Also, you have {instance.receiver_user_replies.filter(final_decision = 'Pending').count()-1} more replies. Check out your replies.'

            elif(not invitations.exists() and not replies.exists()):
                instance.notifications = '-'
            instance.save(update_fields=['notifications'])
            

        rep = super().to_representation(instance)
        check_if_path_has_user_pk = True if str(self.context.get('request').path).rsplit('/')[2].isdigit() else False

        if(instance and instance.organization is not None or instance.role == 'Admin'):
            rep.pop('available_for_work' , None)
        
        if(not instance.organization):
            rep['organization'] = '-'

        if(check_if_path_has_user_pk):
            if(instance):
                if(not instance.notifications):
                    rep['notifications'] = '-'

                else:
                    rep['notifications'] = instance.notifications
                    
        else:
            rep.pop('notifications' , None)
            rep.pop('sumbit_resignation' , None)
        
        rep.pop('request_to_join' , None)
        rep.pop('admin_successor' , None)

        return rep












class OrganizationSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    notifications = serializers.CharField(read_only=True)

    class Meta:
        model = Organization
        fields = ['id' , 'name' , 'location' , 'contact_email' , 'organization_type' , 'established_date' , \
                  'members' , 'invite_user' , 'fire_user' , 'hiring' , 'notifications']

    

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        user = CustomUser.objects.filter(id = self.context.get("user_id")).first()
        if(user):
            if(request.method in ['PATCH' , 'PUT']):
                if(not self.context.get('id')):
                    raise serializers.ValidationError('Organization not found.') 
                organization = Organization.objects.filter(id = self.context.get('id')).first()
                invite_user_queryset = CustomUser.objects.filter(role__in = ['Manager' , 'Driver'] , available_for_work=True , organization__isnull=True) \
                                                         .exclude(Q(receiver_user_invitations__status = 'Pending' , \
                                                                  receiver_user_invitations__sender_organization = organization)) \
                                                         .exclude(sender_user_invitations__status='Pending' , sender_user_invitations__receiver_organization=organization , \
                                                                  sender_user_invitations__reason = 'user_join').exclude(receiver_user_replies__final_decision = 'Pending') \
                                                         .exclude(Q(id__in = Reply.objects.filter(receiver_organization=organization , final_decision = 'Pending').values_list('receiver_user__id' , flat=True)))

                if(not CustomUser.objects.filter(role__in = ['Manager' , 'Driver'] , organization = organization)):
                    fields.pop('fire_user' , None)
            
                else:
                    deleted_user_queryset = CustomUser.objects.filter(organization = organization).exclude(role__in = ['Admin'])
                    fields['fire_user'] = serializers.PrimaryKeyRelatedField(many=True , queryset = deleted_user_queryset , required=False)
                
            else:
                fields.pop('fire_user' , None)
                invite_user_queryset = CustomUser.objects.filter(role__in = ['Manager' , 'Driver'] , available_for_work=True , organization__isnull=True)

            organization = Organization.objects.filter(id = self.context.get('id')).first()
            if(not invite_user_queryset.exists() or not CustomUser.objects.filter(role__in = ['Manager' , 'Driver'] , available_for_work=True)):
                fields.pop('invite_user' , None)

            else:
                fields['invite_user'] = serializers.PrimaryKeyRelatedField(many=True , queryset = invite_user_queryset , required=False)

            

        return fields




    def get_members(self , obj):
        members_of_org = []
        # Firstly, we add the admin of organization
        admin = obj.members.filter(role='Admin').first()
        members_of_org.append(admin.username +  ' (' + admin.role + ')')
        for user in obj.members.exclude(role='Admin'):
            members_of_org.append(user.username + ' (' + user.role + ')')
        return ' , '.join(members_of_org)




    def validate(self , data):
        name = data.get('name')
        est_date = data.get('established_date')

        if(not name.isalpha()):
            raise serializers.ValidationError('Organization name must contain only letters.')

        if(est_date > date.today()):
            raise serializers.ValidationError('Established date cannot exceed the current date')
        return data
    

    def to_representation(self , instance):
        rep = super().to_representation(instance)
        user = CustomUser.objects.filter(id=self.context.get('user_id')).first()

        if(user and instance):
            invitations = Invitation.objects.filter(receiver_organization = instance , status='Pending')
            replies = Reply.objects.filter(receiver_organization = instance , final_decision='Pending')
            
            if(invitations.exists()):
                org_notifications = invitations.last().receiver_organization_notification

                if(instance.receiver_org_invitations.filter(status = 'Pending').count() == 1):
                    instance.notifications = f'{org_notifications} Check out your received-invitations.'
                elif(instance.receiver_org_invitations.filter(status = 'Pending').count() > 1):
                    instance.notifications = f'{org_notifications} Also, you have {instance.receiver_org_invitations.filter(status = 'Pending').count()-1} more notifications. Check out your received-invitations.'
                else:
                    instance.notifications = '-'

            if(replies.exists()):
                last_reply = replies.last().receiver_organization_notification

                if(instance.receiver_org_replies.filter(final_decision = 'Pending').count() == 1):
                    instance.notifications = f'{last_reply} Check out your replies.'
                elif(instance.receiver_org_replies.filter(final_decision = 'Pending').count() > 1):
                    instance.notifications = f'{last_reply} Also, you have {instance.receiver_org_replies.filter(final_decision = 'Pending').count()-1} more replies. Check out your replies.'

            elif(not invitations.exists() and not replies.exists()):
                instance.notifications = '-'
            instance.save(update_fields=['notifications'])

        if(CustomUser.objects.filter(organization=instance , role='Driver' , id=self.context.get('user_id')).first()):
            rep.pop('hiring')

        if(instance.notifications is None):
            rep['notifications'] = '-'
        
        else:
            if(not user.role == 'Admin'):
                rep.pop('notifications' , None)

        rep.pop('invite_user' , None)
        rep.pop('fire_user' , None)
        return rep













class BinSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Bin
        fields = ['id' , 'organization' , 'location' , 'bin_type' , 'capacity' , 'current_fill_level' , \
                  'threshold_level' , 'random_current_fill_level' , 'level' , 'created_at']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')

        if(request and request.method in ['PUT' , 'PATCH']):
            fields['location'].read_only = True
            fields['capacity'].read_only = True
            fields['bin_type'].read_only = True

        if(request and request.method == 'POST'):
            fields['random_current_fill_level'].read_only = True

        fields['level'].read_only = True
        fields['current_fill_level'].read_only = True
        fields['threshold_level'].read_only = True

        return fields


    def get_organization(self, obj):
        return obj.organization.name


    def get_created_at(self , obj):
        local_time = timezone.localtime(obj.created_at)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")
    


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
        rep.pop('random_current_fill_level')
        rep.pop('threshold_level')
        return rep








class TruckSerializer(serializers.ModelSerializer):
    license_plate = serializers.CharField(read_only=True)
    current_load = serializers.DecimalField(max_digits=10 , decimal_places=2 , read_only=True)
    status = serializers.CharField(read_only=True)
    speed = serializers.IntegerField()
    organization = serializers.SerializerMethodField()
    location = serializers.CharField(required=True)
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Truck
        fields = ['id' , 'organization' , 'license_plate' , 'location' , 'base_station' , 'waste_transfer_station' , 'capacity' , 'current_load' , \
                  'speed_category' , 'speed' , 'status' , 'level' , 'created_at' , 'message' , 'unloading_time' , 'back_to_base_time']

    def get_fields(self):
        fields = super().get_fields()
        org_id = self.context.get('organization_pk')
        first_truck = Truck.objects.filter(organization__id = org_id).first()

        if(first_truck and self.instance != first_truck):
            fields['base_station'].read_only = True
            fields['waste_transfer_station'].read_only = True
        
        fields['level'].read_only = True
        fields['speed'].read_only = True
        fields['message'].read_only = True
        fields['unloading_time'].read_only = True
        fields['back_to_base_time'].read_only = True
        return fields
    

    def get_organization(self , obj):
        return obj.organization.name
    

    def get_created_at(self , obj):
        local_time = timezone.localtime(obj.created_at)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")
    


    def __init__(self , *args , **kwargs):
        super().__init__(*args , **kwargs)
        org_id = self.context.get('organization_pk')
        
        if(org_id):
            org = Organization.objects.filter(id=org_id).first()
            if(org):
                location = org.location
                self.fields['location'].help_text = f'Provide an address in {location}. eg: (Address), {location}'
                self.fields['base_station'].help_text = f'Provide a base station point for the truck.'
                self.fields['waste_transfer_station'].help_text = f'Provide a waste transfer station point for the truck.'




    def create(self , validated_data):
        org_id = self.context.get('organization_pk')
        first_truck = Truck.objects.filter(organization__id = org_id).first()
        
        if(first_truck):
            validated_data.setdefault('base_station' , first_truck.base_station)
            validated_data.setdefault('waste_transfer_station' , first_truck.waste_transfer_station)

        return super().create(validated_data)





    def to_representation(self , instance):
        rep = super().to_representation(instance)
        rep['current_load'] = f'{instance.current_load:.1f}'

        if(float(instance.current_load) >= instance.capacity - 200 and float(instance.current_load) < instance.capacity - 50):
            rep['status'] = 'Almost full'

        if(float(instance.current_load) >= instance.capacity - 50 and float(instance.current_load) <= instance.capacity):
            rep['status'] = 'Full'

        if(instance.message == ''):
            rep.pop('message')
        
        rep.pop('unloading_time')
        rep.pop('back_to_base_time')
            
        return rep















class PickUpRequestSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)    
    picked_weight = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=2)
    distance = serializers.SerializerMethodField()
    expected_time = serializers.SerializerMethodField()
    route = serializers.SerializerMethodField()
    truck_speed = serializers.SerializerMethodField()
    requested_at = serializers.SerializerMethodField()
    pickup_at = serializers.SerializerMethodField()
    warnings = serializers.SerializerMethodField()

    class Meta:
        model = PickUpRequest
        fields = ['id' , 'organization' , 'urgency_level' , 'auto_assign_all' , 'bin' , 'truck' , 'picked_weight' , 'auto_assign_truck' , \
                  'scheduled_at' , 'now' , 'distance' , 'expected_time' , 'truck_speed' , 'route' , 'requested_at' , 'pickup_at' , 'status' , 'warnings']

    def get_fields(self):
        fields = super().get_fields()
        fields['urgency_level'].read_only = True

        return fields
    

    def get_urgency_level(self , obj):
        return obj.urgency_level


    def get_organization(self , obj):
        if(obj.organization.name):
            return obj.organization.name
        return None
        

    def get_requested_at(self , obj):
        local_time = timezone.localtime(obj.requested_at)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")


    def get_pickup_at(self , obj):
        local_time = timezone.localtime(obj.pickup_at)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")



    def get_distance(self , obj):
        return obj.distance
    

    def get_scheduled_at(self , obj):
        local_time = timezone.localtime(obj.scheduled_at)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")
    

    def get_expected_time(self , obj):
        return obj.expected_time
    


    def get_route(self , obj):
        if(obj.truck and obj.bin):
            return f'{obj.truck.location}  ->  {obj.bin.location}'



    def get_truck_speed(self , obj):
        if(obj.truck):
            return obj.truck.speed
        return None



    def get_warnings(self , obj):
        if(obj.warnings):
            return f'⚠️ {obj.warnings}'
        return None


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

        if(now and scheduled_at):
            raise serializers.ValidationError('Selecting both \'now\' and \'scheduled at\' is not permitted.')
        
        if(auto_assign_all and auto_assign_truck):
            raise serializers.ValidationError('Selecting both \'auto_assign_all\' and \'auto_assign_truck at\' is not permitted.')

        if(auto_assign_truck and truck):
            raise serializers.ValidationError('Selecting the \'Auto assign truck\' option while also manually assigning a truck is not allowed.')
        
        if(not now):
            if(not scheduled_at):
                raise serializers.ValidationError('Pickup time is required. Please select either \'Now\' or a scheduled date and time.')
            
            if(scheduled_at < local_time()):
                raise serializers.ValidationError('\'Scheduled at\' time must be set to a future time.')
            
        return data
    


    def to_representation(self , instance):
        rep = super().to_representation(instance)

        truck_ = instance.truck
        bin_ = instance.bin
        distance = instance.distance
        auto_assign_all = instance.auto_assign_all
        auto_assign_truck = instance.auto_assign_truck

        if(distance == -1):
            if(auto_assign_truck or auto_assign_all):
                rep['truck'] = 'Calculating... Please refresh in a bit.'
                rep['route'] = 'Calculating... Please refresh in a bit.'
                rep['truck_speed'] = 'Calculating... Please refresh in a bit.'

            if(auto_assign_all):
                rep['bin'] = 'Calculating... Please refresh in a bit.'

            rep['distance'] = 'Calculating... Please refresh in a bit.'
            rep['expected_time'] = 'Calculating... Please refresh in a bit.'
            rep['picked_weight'] = 'Calculating... Please refresh in a bit.'
            
            if(instance.now):
                rep['pickup_at'] = 'Calculating... Please refresh in a bit.'
            else:
                rep['pickup_at'] = self.get_scheduled_at(instance)
        
        elif(instance.status == 'Aborted'):
            rep.pop('truck')
            rep.pop('route')
            rep.pop('pickup_at')
            rep.pop('distance')
            rep.pop('expected_time')
            rep.pop('truck_speed')
            rep.pop('urgency_level')
            rep.pop('bin')
            rep.pop('picked_weight')
    

        else:
            rep['urgency_level'] = self.get_urgency_level(instance)
            rep['distance'] = f'{self.get_distance(instance):.1f} meters'
            rep['expected_time'] = f'{self.get_expected_time(instance):.1f} seconds'
            rep['pickup_at'] = self.get_pickup_at(instance)

        rep['requested_at'] = self.get_requested_at(instance)

        if(truck_ and bin_):
            rep['truck'] = f'{truck_.license_plate}'
            rep['bin'] = f'{bin_.bin_type} / {bin_.location}'

        if(instance.now):
            rep.pop('scheduled_at')


        if(not instance.now):
            rep.pop('now')

        if(not instance.warnings):
            rep.pop('warnings')
        
        
        return rep










class InvitationSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only = True)
    sender_user_notification = serializers.CharField(read_only=True)
    receiver_user_notification = serializers.CharField(read_only=True)
    sender_organization_notification = serializers.CharField(read_only=True)
    receiver_user_notification = serializers.CharField(read_only=True)
    created_at = serializers.SerializerMethodField()  
    updated_at = serializers.SerializerMethodField()  
    notification = serializers.SerializerMethodField(read_only=True)
    select = serializers.PrimaryKeyRelatedField(queryset=Invitation.objects.all() , required=False)

    class Meta:
        model = Invitation
        fields = ['id' , 'select' , 'notification' , 'sender_user_notification' , 'receiver_user_notification' , 'sender_organization_notification' , \
                  'receiver_user_notification' , 'status' , 'created_at' , 'updated_at' , 'accept' , 'decline' , 'cancel']
        
        extra_kwargs = {
                            'sender_user':           {'write_only': False , 'required': False} ,
                            'sender_organization':   {'write_only': False , 'required': False} ,
                            'receiver_user':         {'write_only': False , 'required': False} ,
                            'receiver_organization': {'write_only': False , 'required': False} ,
                            'reason':                {'write_only': False , 'required': False}
                       }




    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        current_user_id = self.context.get('user_id')

        if('received-invitations' in request.path):
            fields.pop('cancel' , None)
            
            if(request and 'organizations' not in request.path):
                if(current_user_id and Invitation.objects.filter(receiver_user=current_user_id , status = 'Pending').exists()):
                    fields['select'] = serializers.PrimaryKeyRelatedField(queryset=Invitation.objects.filter(status='Pending' , receiver_user=current_user_id) , required=False)

                elif(not Invitation.objects.filter(receiver_user=current_user_id , status = 'Pending').exists()):
                    fields.pop('accept' , None)
                    fields.pop('decline' , None)
                    fields.pop('select' , None)

            elif(request and 'organizations' in request.path):
                org_id = self.context.get('organization_id')

                if(org_id and Invitation.objects.filter(receiver_organization=org_id , status = 'Pending').exists()):
                    fields['select'] = serializers.PrimaryKeyRelatedField(queryset=Invitation.objects.filter(status='Pending' , receiver_organization=org_id) , required=False)

                elif(not Invitation.objects.filter(receiver_organization=org_id , status = 'Pending').exists()):
                    fields.pop('accept' , None)
                    fields.pop('decline' , None)
                    fields.pop('select' , None)
                   
        elif('sent-invitations' in request.path):
            fields.pop('accept' , None)
            fields.pop('decline' , None)
            org_id = self.context.get('organization_id')

            if( (request and 'organizations' not in request.path and not Invitation.objects.filter(sender_user=current_user_id , status = 'Pending').exists() ) or \
                (request and 'organizations' in request.path and not Invitation.objects.filter(sender_organization=org_id , status = 'Pending').exists() )):
                fields.pop('select' , None)
                fields.pop('cancel' , None)
            
            else:
                if(request and 'organizations' in request.path):
                    fields['select'] = serializers.PrimaryKeyRelatedField(queryset=Invitation.objects.filter(status='Pending' , sender_organization=org_id) , required=False)

                elif(request and 'organizations' not in request.path):
                    fields['select'] = serializers.PrimaryKeyRelatedField(queryset=Invitation.objects.filter(status='Pending' , sender_user=current_user_id) , required=False)

        return fields
    



    def get_created_at(self , obj):
        local_time = timezone.localtime(obj.created_at)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")

    

    def get_updated_at(self , obj):
        local_time = timezone.localtime(obj.updated_at)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")


    def get_notification(self, obj):
        return getattr(obj , 'notification' , None)



    def to_representation(self , instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        
        if(instance.reason == 'org_fires_user'):
            rep.pop('updated_at' , None)

        if(instance.status == 'Pending'):
            rep.pop('updated_at' , None)
        rep.pop('accept' , None)
        rep.pop('decline' , None)
        rep.pop('cancel' , None)
        rep.pop('sender_user' , None)
        rep.pop('sender_organization' , None)
        rep.pop('receiver_user' , None)
        rep.pop('receiver_organization' , None)
        rep.pop('sender_user_notification' , None)
        rep.pop('receiver_organization_notification' , None)
        rep.pop('sender_organization_notification' , None)
        rep.pop('receiver_user_notification' , None)
        rep.pop('reason' , None)

        if(request):
            if('received-invitations' in request.path):
                if(not 'organizations' in request.path):
                    rep['notification'] = instance.receiver_user_notification
                else:
                    rep['notification'] = instance.receiver_organization_notification

            elif('sent-invitations' in request.path):
                if(not 'organizations' in request.path):
                    rep['notification'] = instance.sender_user_notification
                else:
                    rep['notification'] = instance.sender_organization_notification
        return rep
    




    def validate(self , data):
        accept = data.get('accept')
        decline = data.get('decline')
        cancel = self.context.get('cancel')
        request = self.context.get('request')
        
        if(request and 'received-invitations' in request.path):
            if(not accept and not decline):
                raise ValidationError('At least one action must be selected.')
            
            if(accept and decline):
                raise ValidationError('Only one action must be selected.')
        
        elif(request and 'sent-invitations' in request.path):
            if(not cancel):
                raise ValidationError('Action not selected.')
            
        return data







    def create(self , validated_data):
        accept = validated_data.get('accept' , None)
        decline = validated_data.get('decline' , None)
        sender_user = self.context.get('sender_user')
        receiver_user = self.context.get('receiver_user')
        sender_organization = self.context.get('sender_organization')
        receiver_organization = self.context.get('receiver_organization')
        sender_notification = self.context.get('sender_notification')
        receiver_notification = self.context.get('receiver_notification')
        reason = self.context.get('reason')
        select = validated_data.get('select')
        cancel = validated_data.get('cancel')


        if(accept or decline):
            user = CustomUser.objects.filter(id=self.context.get('user_id')).first()

            if(not user):
                raise ValidationError('User not found')
            
            selected_invitation = Invitation.objects.filter(id=select.id , status='Pending').first()
            selected_invitation.status = 'Accepted' if(accept) else 'Declined'
            selected_invitation.save()

            org_to_user = Invitation.objects.filter(id=select.id).first().sender_organization and Invitation.objects.filter(id=select.id).first().receiver_user
            user_to_user = Invitation.objects.filter(id=select.id).first().sender_user and Invitation.objects.filter(id=select.id).first().receiver_user
            user_to_org = Invitation.objects.filter(id=select.id).first().sender_user and Invitation.objects.filter(id=select.id).first().receiver_organization
            inv = Invitation.objects.filter(id=select.id).first()
            reason = inv.reason

            # Organization -> User
            if(org_to_user):
                org = Organization.objects.filter(id = Invitation.objects.filter(id=select.id).first().sender_organization.id).first()
                receiver_user = CustomUser.objects.filter(id = Invitation.objects.filter(id=select.id).first().receiver_user.id).first()

                if(reason == 'org_invites_user'):                          
                    if(accept):
                        message = f'User \'{receiver_user.username}\' accepted the invitation from \'{org.name}\'.'
                        
                    else:
                        message = f'User \'{receiver_user.username}\' declined the invitation to join.'

                    reply = Reply.objects.create(receiver_organization=org , invitation=inv , message=message) 
                    if(accept):
                        reply.receiver_organization_notification = f'User \'{inv.receiver_user}\' accepted the invitation.'
                        reply.save(update_fields=['receiver_organization_notification'])

                    if(decline):
                        reply.final_decision = 'Declined'
                        reply.save(update_fields=['final_decision'])

            
            # User -> User
            if(user_to_user):
                receiver_user = CustomUser.objects.filter(id = Invitation.objects.filter(id=select.id).first().receiver_user.id).first()
                sender_user = CustomUser.objects.filter(id = Invitation.objects.filter(id=select.id).first().sender_user.id).first()
                org = sender_user.organization

                if(reason == 'admin_successor'):                    
                    # Make 'receiver_user' the new admin and remove 'sender_user' from organization
                    if(accept):
                        message = f'User \'{receiver_user.username}\' accepted the role-transfer invitation and now is the new admin of \'{org.name}\' organization.'
                    
                    elif(decline):
                        message = f'User \'{receiver_user.username}\' rejected the role-transfer invitation.'

                    reply = Reply.objects.create(receiver_user=sender_user , invitation=inv , message=message)
                    
                    if(accept):
                        reply.receiver_user_notification = f'User \'{inv.receiver_user}\' accepted the role-transfer invitation.'
                        reply.save(update_fields=['receiver_user_notification'])

                    if(decline):
                        reply.final_decision = 'Declined'
                        reply.save(update_fields=['final_decision'])

                    
                        

            
            # User -> Organization
            elif(user_to_org):
                org = Organization.objects.filter(id = Invitation.objects.filter(id=select.id).first().receiver_organization.id).first()
                sender_user = CustomUser.objects.filter(id = Invitation.objects.filter(id=select.id).first().sender_user.id).first()

                if(reason == 'user_join'):
                    if(decline):
                        message = f'\'{org.name}\' organization has decided not to move forward with your application.'
                    
                    elif(accept):
                        message = f'Your request has been approved by \'{org.name}\' organization.'

                    reply = Reply.objects.create(receiver_user=sender_user , invitation=inv , message=message)
                    if(accept):
                        reply.receiver_user_notification = f'Your request has been approved by \'{org.name}\' organization.'
                        reply.save(update_fields=['receiver_user_notification'])

                    if(decline):
                        reply.final_decision = 'Declined'
                        reply.save(update_fields=['final_decision'])
                    
                elif(reason == 'user_resignation'):
                    sender_user.sumbit_resignation = False
                    sender_user.save(update_fields=['sumbit_resignation'])
                    answer = 'declined' if decline else 'accepted'
                    message = f'After consideration, the organization has {answer} your resignation request.'
                    if(accept):
                        org.members.remove(sender_user)
                
                    reply = Reply.objects.create(receiver_user=sender_user , invitation=inv , message=message)
                    if(accept):
                        invit = Invitation.objects.filter(receiver_user = sender_user , status='Pending')
                        for r in invit.all():
                            r.status = 'Aborted'
                            r.save(update_fields=['status'])

                    reply.final_decision = 'Accepted' if accept else 'Declined'
                    reply.save(update_fields=['final_decision'])
            
            return selected_invitation
        



        # cancel sent invitation
        invitation_id = validated_data.get('invitation')
        if(cancel):
            cancel_sent_inv = Invitation.objects.filter(id=invitation_id).first()
            cancel_sent_inv.status = 'Cancelled'
            cancel_sent_inv.save(update_fields=['status'])
            return cancel_sent_inv



        
        # invitation: user -> user
        if(sender_user and receiver_user):
            invitation = Invitation.objects.create(sender_user=sender_user , receiver_user=receiver_user , reason=reason)
            invitation.receiver_user_notification = receiver_notification
            invitation.save(update_fields=['receiver_user_notification'])
            invitation.sender_user_notification = sender_notification
            invitation.save(update_fields=['sender_user_notification'])

        # invitation: user -> organization
        elif(sender_user and receiver_organization):
            invitation = Invitation.objects.create(sender_user=sender_user , receiver_organization=receiver_organization , reason=reason)
            invitation.receiver_organization_notification = receiver_notification
            invitation.save(update_fields=['receiver_organization_notification'])
            invitation.sender_user_notification = sender_notification
            invitation.save(update_fields=['sender_user_notification'])

        # invitation: organization -> user
        elif(sender_organization and receiver_user):
            invitation = Invitation.objects.create(sender_organization=sender_organization , receiver_user=receiver_user , reason=reason)
            if(invitation.reason == 'org_fires_user'):
                receiver_user.sumbit_resignation = False
                receiver_user.save(update_fields=['sumbit_resignation'])
                invitation.status = 'Fired'
                invitation.save(update_fields=['status'])

                # user may sent some invitations about resigning from their organization, but organization first fire user, so user's invitation must not be pending anymore, but aborted
                remaining_org_inv_of_fired_user = Invitation.objects.filter(receiver_organization=sender_organization , sender_user=receiver_user , status='Pending')
                if(remaining_org_inv_of_fired_user.exists()):
                    for inv in remaining_org_inv_of_fired_user.all():
                        inv.status = 'Aborted'
                        inv.save(update_fields=['status'])

            invitation.receiver_user_notification = receiver_notification
            invitation.save(update_fields=['receiver_user_notification'])
            invitation.sender_organization_notification = sender_notification
            invitation.save(update_fields=['sender_organization_notification'])
        
        

        if(receiver_user):
            if(receiver_user.receiver_user_invitations.filter(status = 'Pending').count() == 1):
                receiver_user.notifications = f'{receiver_notification} Check out your received-invitations.'
            elif(receiver_user.receiver_user_invitations.filter(status = 'Pending').count() > 1):
                receiver_user.notifications = f'{receiver_notification} Also, you have {receiver_user.receiver_user_invitations.filter(status = 'Pending').count()-1} more notifications. Check out your received-invitations.'
            else:
                receiver_user.notifications = None
            receiver_user.save(update_fields=['notifications'])

        if(receiver_organization):
            if(receiver_organization.receiver_org_invitations.filter(status = 'Pending').count() == 1):
                receiver_organization.notifications = f'{receiver_notification} Check out your received-invitations.'
            elif(receiver_organization.receiver_org_invitations.filter(status = 'Pending').count() > 1):
                receiver_organization.notifications = f'{receiver_notification} Also, you have {receiver_organization.receiver_org_invitations.filter(status = 'Pending').count()-1} more notifications. Check out your received-invitations.'
            else:
                receiver_organization.notifications = None
            receiver_organization.save(update_fields=['notifications'])
        
        return invitation
    



    










class ReplySerializer(serializers.ModelSerializer):
    created_at = serializers.SerializerMethodField() 
    message = serializers.CharField(read_only=True)
    select = serializers.PrimaryKeyRelatedField(queryset=Reply.objects.filter(final_decision='Pending') , required=False)
    final_decision = serializers.CharField(read_only = True)

    class Meta:
        model = Reply
        fields = ['id' , 'message' , 'created_at' , 'select' , 'accept' , 'decline' , 'final_decision']

        extra_kwargs = {
                            'invitation': {'write_only': False , 'required': False}
                       }

    def get_fields(self):
        fields = super().get_fields()

        user = CustomUser.objects.filter(id=self.context.get('user_id')).first()

        if(not user):
            raise ValidationError('User not found.')
        
        if(not Reply.objects.filter(final_decision='Pending').exists()):
            fields.pop('accept' , None)
            fields.pop('decline' , None)
            fields.pop('select' , None)

        return fields


    def get_created_at(self , obj):
        local_time = timezone.localtime(obj.created_at)
        return local_time.strftime("%d/%m/%Y, %H:%M:%S")
    
        

    def to_representation(self , instance):
        rep = super().to_representation(instance)
        
        rep.pop('accept' , None)
        rep.pop('decline' , None)

        return rep
    


    def validate(self , data):
        accept = data.get('accept')
        decline = data.get('decline')
        
        if(not accept and not decline):
            raise ValidationError('At least one action must be selected.')
        
        if(accept and decline):
            raise ValidationError('Only one action must be selected.')
            
        return data
    




    def create(self , validated_data):
        request = self.context.get('request')
        invitation_id = validated_data.get('invitation')
        accept = validated_data.get('accept')
        decline = validated_data.get('decline')
        
        inv = Invitation.objects.filter(id=invitation_id).first()
        reply = Reply.objects.filter(invitation = inv).first()
        respones = []
        respones.clear()

        if(request and 'organizations' not in request.path):
            if(inv.reason == 'user_join'):
                if(accept):
                    if(not inv.sender_user.organization):
                        message = f'User \'{inv.sender_user}\' just became a member of \'{inv.receiver_organization}\' organization.'
                        reply.final_decision = 'Accepted'
                        reply.save(update_fields=['final_decision'])
                        respones.append(reply)

                        rec_org_reply = Reply.objects.create(invitation = reply.invitation , receiver_organization = inv.receiver_organization , message = message)
                        rec_org_reply.final_decision = 'Accepted'
                        rec_org_reply.save(update_fields=['final_decision'])
                        inv.receiver_organization.members.add(inv.sender_user) # add user to organization
                        
                        remaining_pending_replies = Reply.objects.filter(final_decision='Pending').exclude(id=reply.id)

                        for rem_reply in remaining_pending_replies.all():
                            rem_reply.final_decision = 'Aborted'
                            rem_reply.save(update_fields=['final_decision'])
                            respones.append(rem_reply)

                            rem_message = f'The request was automatically aborted following the \'{inv.sender_user}\' decision to proceed with another organization.'
                            rem_reply_to_receiver = Reply.objects.create(invitation=rem_reply.invitation , receiver_organization=rem_reply.invitation.receiver_organization , message=rem_message)
                            rem_reply_to_receiver.final_decision = 'Aborted'
                            rem_reply_to_receiver.save(update_fields=['final_decision'])


                    else:
                        raise ValidationError(f'You are already part of \'{inv.sender_user.organization}\' organization. You need to submit your resignation first.')

                elif(decline):
                    message = f'User \'{inv.sender_user}\' rejected the cooperation invitation.'
                    reply.final_decision = 'Declined'
                    respones.append(reply)
                    reply.save(update_fields=['final_decision'])
                    
                    rec_org_reply = Reply.objects.create(invitation = reply.invitation , receiver_organization = inv.receiver_organization , message = message)
                    rec_org_reply.final_decision = 'Declined'
                    rec_org_reply.save(update_fields=['final_decision'])


            elif(inv.reason == 'admin_successor'):
                sender_user = Invitation.objects.filter(id=invitation_id).first().sender_user
                receiver_user = Invitation.objects.filter(id=invitation_id).first().receiver_user
                org = receiver_user.organization
            
                if(accept):
                    reply.final_decision = 'Accepted'
                    reply.save(update_fields=['final_decision'])
                    org.members.remove(sender_user)
                    receiver_user.role = 'Admin'
                    receiver_user.save(update_fields=['role'])
                    
                    message = f'User {sender_user.username} accepted the role-transfer.'
                    rec_user_reply = Reply.objects.create(invitation = reply.invitation , receiver_user = inv.receiver_user , message = message)
                    rec_user_reply.final_decision = 'Accepted'
                    rec_user_reply.save(update_fields=['final_decision'])

                    invit = Invitation.objects.filter(sender_user=receiver_user , status='Pending')
                    for r in invit.all():
                        r.status = 'Aborted'
                        r.save(update_fields=['status'])    
                    
                elif(decline):
                    reply.final_decision = 'Declined'
                    reply.save(update_fields=['final_decision'])
                    message = f'User {sender_user.username} rejected the role-transfer.'
                    rec_user_reply = Reply.objects.create(invitation = reply.invitation , receiver_user = inv.receiver_user , message = message)
                    rec_user_reply.final_decision = 'Declined'
                    rec_user_reply.save(update_fields=['final_decision'])

                

                

        elif(request and 'organizations' in request.path):
            if(inv.reason == 'org_invites_user'):
                if(accept):
                    message = f'\'{inv.sender_organization}\' organization accepted you as a member.'
                    reply.final_decision = 'Accepted'
                    respones.append(reply)
                    inv.sender_organization.members.add(inv.receiver_user)
                
                elif(decline):
                    message = f'Your acceptance was received, but the \'{inv.sender_organization}\' organization has declined to proceed further.'
                    reply.final_decision = 'Declined'
                    respones.append(reply)
                reply.save(update_fields=['final_decision'])
                
                reply_to_receiver = Reply.objects.create(invitation=inv , receiver_user=inv.receiver_user , message=message)
                if(accept):
                    reply.receiver_user_notification = f'\'{inv.sender_organization}\' organization accepted you as a member.'
                else:
                    reply.receiver_user_notification = f'\'{inv.sender_user}\' organization rejected the invitation to join.'

                reply.save(update_fields=['receiver_user_notification'])
                reply_to_receiver.final_decision = 'Accepted' if accept else 'Declined'
                reply_to_receiver.save(update_fields=['final_decision'])

        
        return respones