from rest_framework import viewsets , status
from rest_framework.response import Response
from .models import *
from .serializers import *
from django.db.models import Count , Q
from rest_framework.exceptions import ValidationError
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json




class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer


    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'users/'
        if(CustomUser.objects.count() == 0):
            return Response(f'There are no users yet. Create one!')
        
        return super().list(request , *args , **kwargs)
    




    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'users/<pk>'
        user_id = self.kwargs.get('pk')

        if(not CustomUser.objects.filter(id=user_id).exists()):
            return Response(f'User #{user_id} does not exist. Update will fail.' , status=404)
        return super().retrieve(request , *args , **kwargs)






    def update(self , request , *args , **kwargs):
        user = CustomUser.objects.filter(id=self.kwargs.get('pk')).first()
        if(not user):
            return Response(f'User was not updated!' , status=403)
        
        serializer = self.get_serializer(CustomUser.objects.get(id=self.kwargs.get('pk')) , data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data , status=200) 










class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer


    def get_queryset(self):
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        orgs_without_users = Organization.objects.annotate(users_count=Count('users')).filter(users_count=0)
        
        if(not user):
            if(Organization.objects.exists()):
                return Organization.objects.all()
            else:
                return Organization.objects.none()
        
        return Organization.objects.filter(Q(users=user) | Q(id__in = orgs_without_users.values_list('id' , flat=True)))

    

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        if(user):
            context['id'] = self.kwargs.get('pk')
            context['user'] = CustomUser.objects.get(id=self.kwargs.get('user_pk'))
            return context




    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'organizations/'
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()

        orgs_without_users = Organization.objects.annotate(users_count=Count('users')).filter(users_count=0)
        if(orgs_without_users.exists()):
            orgs_without_users_list = OrganizationSerializer(orgs_without_users , many=True).data
        
        if(not user):
            return Response(f'User #{user_id} does not exist. Organization will not be created!' , status=404)
            
        
        if(orgs_without_users.exists()):    
            if(not user.organizations.exists()):        
                return Response({'Message':f'There are no organizations for user #{user_id} yet. Create one!' , \
                                 'Available organizations with no users': orgs_without_users_list})

            return Response({'Message': OrganizationSerializer(user.organizations.all() , many=True).data , \
                             'Available organizations with no users': orgs_without_users_list})

        if(user.organizations.count() == 0):
            return Response(f'There are no organizations for user #{user_id} yet. Create one!')
        
        return super().list(request , *args , **kwargs)
       
    



    
    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'organizations/<pk>'
        organization_id = self.kwargs.get('pk')
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id)
        organization = Organization.objects.filter(id=organization_id).first()

        if(not user):
            return Response(f'User #{user_id} does not exist. Organization will not be updated!' , status=404)
        
        elif(not organization):
            return Response(f'Organization #{organization_id} does not exist. Organization will not be updated!' , status=404)
        
        elif(not user.first().organizations.filter(id=organization_id).exists()):
            return Response(f'Organization #{organization_id} does not belong to user #{user_id}. Organization will not be updated!' , status=404)

        return super().retrieve(request , *args , **kwargs)
    

    


    
    
    def create(self , request , *args , **kwargs): # /users/<pk>/organizations/
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        if(not user):
            return Response(f'Organization was not created!' , status=403)
        

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data.get('name')
        location = serializer.validated_data.get('location')
        org_type = serializer.validated_data.get('organization_type')
        est_date = serializer.validated_data.get('established_date')
        contact_email = serializer.validated_data.get('contact_email')
        
        
        orgs_without_users = Organization.objects.annotate(users_count = Count('users')).filter(users_count = 0)
        orgs = Organization.objects.filter(Q(users=user) | Q(id__in = orgs_without_users.values_list('id' , flat=True)))

        orgs_without_users_match = orgs_without_users.filter(name=name , location=location , organization_type=org_type , \
                                                             established_date=est_date , contact_email=contact_email).first()
        
        if(orgs_without_users_match):
            user.organizations.add(orgs_without_users_match)
            org = self.get_serializer(orgs_without_users_match).data
            return Response(org , status=201) 
        
        if(orgs.filter(name=name , location=location , organization_type=org_type , established_date=est_date , contact_email=contact_email)):
            raise serializers.ValidationError(f'This organization already exists.')
            
        if(orgs.filter(contact_email=contact_email)):
            raise serializers.ValidationError(f'This contact email already exists.')
        
        if(orgs.filter(name=name , location=location)):
            raise serializers.ValidationError(f'There is another organization with the same name in {location}.')
        
        organization = serializer.save()
        user.organizations.add(organization) # add the new organization to the user's organizations
        return Response(serializer.data , status=201)
    
    




    def update(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>
        org_id = self.kwargs.get('pk')
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()

        if(not user or (user and not user.organizations.filter(id=org_id).exists())):
            return Response(f'Organization was not updated!' , status=403)
        
        serializer = self.get_serializer(Organization.objects.get(id=org_id) , data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data.get('name')
        location = serializer.validated_data.get('location')
        org_type = serializer.validated_data.get('organization_type')
        est_date = serializer.validated_data.get('established_date')
        contact_email = serializer.validated_data.get('contact_email')
        
        
        orgs_without_users = Organization.objects.annotate(users_count = Count('users')).filter(users_count = 0)
        orgs = Organization.objects.filter(Q(users=user) | Q(id__in = orgs_without_users.values_list('id' , flat=True)))

        if(orgs.filter(name=name , location=location , organization_type=org_type , established_date=est_date , contact_email=contact_email)):
            raise serializers.ValidationError(f'This organization already exists.')
            
        if(orgs.filter(contact_email=contact_email) and Organization.objects.get(id=org_id).contact_email != contact_email):
            raise serializers.ValidationError(f'This contact email already exists.')
        
        if(orgs.filter(name=name , location=location)):
            raise serializers.ValidationError(f'There is another organization with the same name in {location}.')
        
        serializer.save()
        return Response(serializer.data , status=200)












class BinViewSet(viewsets.ModelViewSet):
    serializer_class = BinSerializer
    
    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()

        if(user and organization and user.organizations.filter(id=organization.id)):
            return Bin.objects.filter(organization_id=organization.id)
        return Bin.objects.none()
    



    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'bins/'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()

        if(not user):
            return Response(f'User #{user_id} does not exist. Bin will not be created!' , status=404)
        
        if(not organization):
            return Response(f'Organization #{org_id} does not exist. Bin will not be created!' , status=404)
        
        elif(user.organizations.count() == 0):
            return Response(f'User #{user_id} does not belong to any organization yet. Bin will not be created!' , status=404)
        
        elif(not user.organizations.filter(id=organization.id).exists()):
            return Response(f'User #{user_id} does not belong in organization \'{organization.name}\'. Bin will not be created!' , status=404)
        
        elif(organization.bins.count() == 0):
            return Response(f'There are no bins for \'{organization.name}\' organization yet. Create one!')
        
        return super().list(request , *args , **kwargs)
    



    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'bins/<pk>'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()
        bin_id = self.kwargs.get('pk')
        

        if(not user):
            return Response(f'User #{user_id} does not exist. Bin will not be updated!' , status=404)
        
        if(not organization):
            return Response(f'Organization #{org_id} does not exist. Bin will not be updated!' , status=404)
        
        elif(user.organizations.count() == 0):
            return Response(f'User #{user_id} does not belong to any organization yet. Bin will not be updated!' , status=404)
        
        elif(not user.organizations.filter(id=organization.id).exists()):
            return Response(f'User #{user_id} does not belong in organization \'{organization.name}\'. Bin will not be updated!' , status=404)

        org_bin = organization.bins.filter(id = bin_id).first()
        if(not org_bin):
            return Response(f'Bin #{bin_id} does not belong to organization \'{organization.name}\'. Bin will not be updated!' , status=404)
        
        return super().retrieve(request , *args , **kwargs)
    




    def create(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/bins/
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        organization = Organization.objects.filter(id=org_id).first()


        if(not user or not organization or not user.organizations.filter(id=organization.id).exists()):
            return Response(f'Bin was not created!' , status=403)
        

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization = organization) # connect the organization with the bin
        return Response(serializer.data , status=201)
    




    def update(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/bins/<pk>
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        organization = Organization.objects.filter(id=org_id).first()
        bin_id = self.kwargs.get('pk')

        if(not user or not organization or (user and organization and (not user.organizations.filter(id=org_id).exists()) \
                                                                       or not organization.bins.filter(id = bin_id).first())):
            return Response(f'Bin was not updated!' , status=403)
            
        serializer = self.get_serializer(organization.bins.filter(id = bin_id).first() , data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization = organization)
        return Response(serializer.data , status=200)
    



    
    def perform_create(self , serializer):
        organization = Organization.objects.get(id=self.kwargs.get('organization_pk'))
        serializer.save(organization = organization)


    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['organization_pk'] = self.kwargs.get('organization_pk')
        return context
    












class TruckViewSet(viewsets.ModelViewSet):
    serializer_class = TruckSerializer

    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()

        if(user and organization and user.organizations.filter(id=organization.id).first()):
            return Truck.objects.filter(organization_id=organization.id)
        return Truck.objects.none()
    


    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'trucks/'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()

        if(not user):
            return Response(f'User #{user_id} does not exist. Truck will not be created!' , status=404)
        
        if(not organization):
            return Response(f'Organization #{org_id} does not exist. Truck will not be created!' , status=404)
        
        elif(user.organizations.count() == 0):
            return Response(f'User #{user_id} does not belong to any organization yet. Truck will not be created!' , status=404)
        
        elif(not user.organizations.filter(id=organization.id).exists()):
            return Response(f'User #{user_id} does not belong in organization \'{organization.name}\'. Truck will not be created!' , status=404)
    
        elif(organization.trucks.count() == 0):
            return Response(f'There are no trucks for \'{organization.name}\' organization yet. Create one!')
        
        return super().list(request , *args , **kwargs)
    





    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'trucks/<pk>'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()
        truck_id = self.kwargs.get('pk')
        

        if(not user):
            return Response(f'User #{user_id} does not exist. Truck will not be updated!' , status=404)
        
        if(not organization):
            return Response(f'Organization #{org_id} does not exist. Truck will not be updated!' , status=404)
        
        elif(user.organizations.count() == 0):
            return Response(f'User #{user_id} does not belong to any organization yet. Truck will not be updated!' , status=404)
        
        elif(not user.organizations.filter(id=organization.id).exists()):
            return Response(f'User #{user_id} does not belong in organization \'{organization.name}\'. Truck will not be updated!' , status=404)

        org_truck = organization.trucks.filter(id = truck_id).first()
        if(not org_truck):
            return Response(f'Truck #{truck_id} does not belong to organization \'{organization.name}\'. Truck will not be updated!' , status=404)
        
        return super().retrieve(request , *args , **kwargs)
    

    



    def create(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/trucks/
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        organization = Organization.objects.filter(id=org_id).first()

        if(not user or not organization or not user.organizations.filter(id=organization.id).exists()):
            return Response(f'Truck was not created!' , status=403)

        truck = Truck.objects.filter(organization=organization).first()
        if(truck):
            if(truck.unload):
                truck.current_load = 0
                truck.unload = False
                truck.save()
                
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization = organization) # connect the organization with the truck
        return Response({'Truck':serializer.data} , status=201)
    




    def update(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/trucks/<pk>
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        organization = Organization.objects.filter(id=org_id).first()
        truck_id = self.kwargs.get('pk')

        if(not user or not organization or (user and organization and (not user.organizations.filter(id=org_id).exists()) \
                                                                       or not organization.trucks.filter(id = truck_id).first())):
            return Response(f'Truck was not updated!' , status=403)
                

        serializer = self.get_serializer(organization.trucks.filter(id = truck_id).first() , data=request.data) 
        serializer.is_valid(raise_exception=True)
        truck = serializer.save(organization = organization)

        if(truck):
            if(truck.unload):
                truck.current_load = 0
                truck.unload = False
                truck.save()

        return Response(serializer.data , status=200)
    



    def perform_create(self , serializer):
        organization = Organization.objects.get(id=self.kwargs.get('organization_pk'))
        serializer.save(organization=organization)



    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['organization_pk'] = self.kwargs.get('organization_pk')
        return context










class PickUpRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PickUpRequestSerializer

    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        requested_by = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()

        if(user and requested_by and user.organizations.filter(id=requested_by.id)):
            return PickUpRequest.objects.filter(requested_by=requested_by)
        return PickUpRequest.objects.none()




    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'pickuprequests/'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        requested_by = Organization.objects.filter(id=org_id).first()

        if(not user):
            return Response(f'User #{user_id} does not exist. Pickup request will not be created!' , status=404)
        
        if(not requested_by):
            return Response(f'Organization #{org_id} does not exist. Pickup request will not be created!' , status=404)
        
        elif(user.organizations.count() == 0):
            return Response(f'User #{user_id} does not belong to any organization yet. Pickup request will not be created!' , status=404)
        
        elif(not user.organizations.filter(id=requested_by.id).exists()):
            return Response(f'User #{user_id} does not belong in organization \'{requested_by.name}\'. Pickup request will not be created!' , status=404)
        
        trucks = Truck.objects.filter(organization=requested_by).exists()
        bins = Bin.objects.filter(organization=requested_by).exists()
        
        if(not trucks or not bins):
            var = ''
            if(not trucks and not bins):
                var = 'no trucks nor bins'
            elif(not trucks):
                var = 'no trucks'
            elif(not bins):
                var = 'no bins'
            return Response(f'There are {var} for \'{requested_by.name}\' organization yet. Pickup request will not be created!' , status=400)
        
        if(requested_by.pickup_requests.count() == 0):
            return Response(f'There are no pickup requests for \'{requested_by.name}\' organization yet. Create one!')
        
                 
        return super().list(request , *args , **kwargs)
       






    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'pickuprequests/<pk>'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        requested_by = Organization.objects.filter(id=org_id).first()
        pickup_request_id = self.kwargs.get('pk')
        

        if(not user):
            return Response(f'User #{user_id} does not exist. Pickup request will not be updated!' , status=404)
        
        if(not requested_by):
            return Response(f'Organization #{org_id} does not exist. Pickup request will not be updated!' , status=404)
        
        elif(user.organizations.count() == 0):
            return Response(f'User #{user_id} does not belong to any organization yet. Pickup request will not be updated!' , status=404)
        
        elif(not user.organizations.filter(id=requested_by.id).exists()):
            return Response(f'User #{user_id} does not belong in organization \'{requested_by.name}\'. Pickup request will not be updated!' , status=404)

        org_pickup_request = requested_by.pickup_requests.filter(id = pickup_request_id).first()
        if(not org_pickup_request):
            return Response(f'Pickup request #{pickup_request_id} does not belong to organization \'{requested_by.name}\'. Pickup request will not be updated!' , \
                            status=404)
        
        pickup_requests = PickUpRequest.objects.filter(requested_by=requested_by)

        for pickup in pickup_requests:
            if(pickup and (not pickup.bin or not pickup.truck or not requested_by or not user)):
                var = 'truck' if not pickup.truck else 'bin'
                pickup.delete()
                return Response(f'Pickup request deleted, because {var} removed from this organization.' , status=204)

        
        return super().retrieve(request , *args , **kwargs)
    



    def create(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/pickuprequests/
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        requested_by = Organization.objects.filter(id=org_id).first()
        trucks = Truck.objects.filter(organization=requested_by).exists()
        bins = Bin.objects.filter(organization=requested_by).exists()

        if(not user or not requested_by or not user.organizations.filter(id=requested_by.id).exists()) or not trucks or not bins:
            return Response(f'Pickup request was not created!' , status=403)
        

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pickup_request = serializer.save(requested_by = requested_by) # connect the requested_by (organization) with the pickup request
        self.perform_create(serializer)
        
        message = f'Pickup request #{pickup_request.id} created successfully.'
        return Response(message , status=201)






    def update(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/pickuprequests/<pk>
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        requested_by = Organization.objects.filter(id=org_id).first()
        pickuprequest_id = self.kwargs.get('pk')

        if(not user or not requested_by or (user and requested_by and (not user.organizations.filter(id=org_id).exists()) \
                                                                       or not requested_by.pickup_requests.filter(id = pickuprequest_id).first())):
            return Response(f'Pickup request was not updated!' , status=403)
            
        serializer = self.get_serializer(requested_by.pickup_requests.get(id = pickuprequest_id) , data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(requested_by = requested_by)
        return Response(serializer.data , status=200)
    


    def perform_create(self , serializer):
        requested_by = Organization.objects.get(id=self.kwargs.get('organization_pk'))
        pickup_request = serializer.save(requested_by=requested_by)
        user = CustomUser.objects.get(id=self.kwargs.get('user_pk'))

        if(pickup_request.truck and pickup_request.bin):
            print(pickup_request.truck.current_load)
            print(pickup_request.bin.current_fill_level)
            print(pickup_request.truck.current_load + pickup_request.bin.current_fill_level)
            print(pickup_request.truck.capacity)
            if(pickup_request.truck.current_load + pickup_request.bin.current_fill_level > pickup_request.truck.capacity):
                if(not pickup_request.auto_assign_all and not pickup_request.auto_assign_truck):
                    raise ValidationError(f'Truck \'{pickup_request.truck.license_plate}\' cannot pickup the {str(pickup_request.bin.bin_type).lower()} bin at \'{pickup_request.bin.location}\', due to full load. Empty the truck\'s load or search for another bin.')


            if(pickup_request.bin.current_fill_level == 0):
                raise ValidationError(f'{pickup_request.bin.bin_type} bin at \'{pickup_request.bin.location}\' is already empty.')


            schedule , _= IntervalSchedule.objects.get_or_create(every=5 , period=IntervalSchedule.SECONDS)

            PeriodicTask.objects.create(interval=schedule , name=f"pickup-task{pickup_request.id}-for-org-{requested_by.id}" , \
                                        task="smart_waste_app.tasks.create_pickup_request" , args=json.dumps([user.id , requested_by.id]))
        





    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['pickup_request_pk'] = self.kwargs.get('pk')
        return context



    def get_serializer(self , *args , **kwargs):
        serializer = super().get_serializer(*args , **kwargs)
        organization = Organization.objects.filter(id = self.kwargs.get('organization_pk')).first()

        if(hasattr(serializer , 'fields')):
            serializer.fields['bin'].queryset = Bin.objects.filter(organization_id = organization.id)
            serializer.fields['truck'].queryset = Truck.objects.filter(organization_id = organization.id)

        return serializer











class CollectionViewSet(viewsets.ReadOnlyModelViewSet): # ReadOnlyModelViewSet -> Only for reading collections
    serializer_class = CollectionSerializer

    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        organization = Organization.objects.filter(id=self.kwargs.get('requested_by_pk')).first()

        if(user and organization and user.organizations.filter(id=organization.id)):
            return Collection.objects.filter(organization_id=organization.id)
        return Collection.objects.none()
    



    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'collections/'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()

        if(not user):
            return Response(f'User #{user_id} does not exist.' , status=404)
        
        if(not organization):
            return Response(f'Organization #{org_id} does not exist.' , status=404)
        
        elif(user.organizations.count() == 0):
            return Response(f'User #{user_id} does not belong to any organization yet.' , status=404)
        
        elif(not user.organizations.filter(id=organization.id).exists()):
            return Response(f'User #{user_id} does not belong in organization \'{organization.name}\'.' , status=404)
    
        pickup_request = PickUpRequest.objects.filter(requested_by = organization).first()
        
        if(not pickup_request):
            return Response(f'There are no collections for organization \'{organization.name}\', because no pickup requests created yet.' , status=400)
        
        return super().list(request , *args , **kwargs)
    





    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'collections/<pk>'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()
        collection_id = self.kwargs.get('pk')
        

        if(not user):
            return Response(f'User #{user_id} does not exist.' , status=404)
        
        if(not organization):
            return Response(f'Organization #{org_id} does not exist.' , status=404)
        
        elif(user.organizations.count() == 0):
            return Response(f'User #{user_id} does not belong to any organization yet.' , status=404)
        
        elif(not user.organizations.filter(id=organization.id).exists()):
            return Response(f'User #{user_id} does not belong in organization \'{organization.name}\'.' , status=404)

        pickup_request = PickUpRequest.objects.filter(requested_by = organization).first()
        
        if(not pickup_request):
            return Response(f'There are no pickup requests for organization \'{organization.name}\' yet. Collection #{collection_id} does not exist.' , status=400)
        
        pickup_request_collection = pickup_request.collections.filter(id = collection_id).first()
        
        if(pickup_request and not pickup_request_collection):
            return Response(f'Collection #{collection_id} does not exist' , status=404)
        
        return super().retrieve(request , *args , **kwargs)