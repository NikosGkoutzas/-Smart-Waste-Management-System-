from rest_framework import viewsets , status , mixins
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError , PermissionDenied
from .models import *
from .serializers import *
from django.db.models import Q
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json
from .permissions import RoleBasedPermission , AllowActions
from smart_waste_app.tasks import calculate_distance_task
from datetime import timedelta





class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.select_related('organization') 
    '''
        It will return all users, just like CustomUser.objects.all().
        The difference is that now it will also have prefetched (profortwsei) the organizations for each one.
    '''

    serializer_class = CustomUserSerializer
    permission_classes = [AllowActions]



    def get_permissions(self):
        return [AllowActions()]
    



    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'users/'
        if(CustomUser.objects.count() == 0):
            return Response(f'There are no users yet. Create one!')
        
        return super().list(request , *args , **kwargs)
    




    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'users/<pk>'
        user_id = self.kwargs.get('pk')

        if(not CustomUser.objects.filter(id=user_id).exists()):
            raise PermissionDenied(f'User #{user_id} does not exist.')
        return super().retrieve(request , *args , **kwargs)






    def update(self , request , *args , **kwargs):
        user = CustomUser.objects.filter(id=self.kwargs.get('pk')).first()
        if(not user):
            return Response(f'User was not updated!' , status=403)
        
        serializer = self.get_serializer(CustomUser.objects.get(id=self.kwargs.get('pk')) , data=request.data)
        serializer.is_valid(raise_exception=True)

        if(CustomUser.objects.filter(username = serializer.validated_data.get('username')).exclude(id=user.id)):
            raise ValidationError('This username already exists.')

        user_data = serializer.save()
        org = user_data.organization

        # USER -> ORGANIZATION
        # user sends join request(s) to organization(s)
        if(serializer.validated_data.get('request_to_join', [])):
            for org_join in user_data.request_to_join.all():
                org = Organization.objects.filter(id=org_join.id).first() 
                receiver_notification = f'User \'{user_data.username}\' wants to join the organization.'
                sender_notification = f'You sent a join request to \'{org}\' organization.'
                context = {'request': request , 'receiver_notification': receiver_notification , 'sender_notification': sender_notification , \
                            'sender_user': user , 'receiver_organization': org , 'reason': 'user_join'}
                data = {}
                inv = InvitationSerializer(data=data , context=context)
                inv.is_valid(raise_exception=True)
                inv.save()


        # USER -> ORGANIZATION
        # user wants to submit resignation from their organization
        if(user_data.sumbit_resignation and not Invitation.objects.filter(sender_user=user , receiver_organization=org , status='Pending').exists()): 
            receiver_notification = f'User \'{user_data.username}\' wants to submit their resignation from the organization.'
            sender_notification = f'You sent a resignation request to \'{org}\' organization.'
            context = {'request': request , 'receiver_notification': receiver_notification , 'sender_notification': sender_notification , \
                        'sender_user': user , 'receiver_organization': org , 'reason': 'user_resignation'}
            data = {}
            inv = InvitationSerializer(data=data , context=context)
            inv.is_valid(raise_exception=True)
            inv.save()

        
        
        # USER -> USER
        # user (admin) wants to transfer their admin role to a member of their organization, in order to leave
        if(getattr(user_data , 'admin_successor' , None)):
            receiver_notification = f'Admin \'{user_data.username}\' would like to transfer their role for \'{user_data.organization.name}\' organization to you.'
            sender_notification = f'You sent a role-transfer request \'{user_data.admin_successor}\'.'

            context = {'request': request , 'receiver_notification': receiver_notification , 'sender_notification': sender_notification , \
                        'sender_user': user  , 'receiver_user': user_data.admin_successor , 'reason': 'admin_successor'}
            data = {}            
            inv = InvitationSerializer(data=data , context=context)
            inv.is_valid(raise_exception=True)
            inv.save()
            
        
        serializer = self.get_serializer(CustomUser.objects.get(id=self.kwargs.get('pk')))
        return Response(serializer.data , status=200) 




    def get_serializer_context(self , *args , **kwargs):
        context = super().get_serializer_context()
        context['id'] = self.kwargs.get('pk')
        return context
    



    def destroy(self , *args , **kwargs):
        user_id = self.kwargs.get('pk')
        user = CustomUser.objects.filter(id=user_id).first()
        if(not user):
            raise ValidationError('User not found.')

        if(user.role == 'Admin' and user.organization):
            user_org = CustomUser.objects.filter(role='Admin' , id=user_id).first().organization.name
            return Response(f'Deletion is not permitted until a replacement admin has been assigned to the \'{user_org}\' organization.' , status=403)

        user.delete()
        return Response(f'User #{user_id} deleted successfully.')











class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [AllowActions]

    def get_queryset(self):
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        
        if(user):
            if(Organization.objects.exists()):
                return Organization.objects.all()
            else:
                return Organization.objects.none()

        return Organization.objects.filter(members=user)




    def get_permissions(self):
        return [AllowActions()]




    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['user_id'] = self.kwargs.get('user_pk')
        context['id'] = self.kwargs.get('pk')
        return context




    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'organizations/'
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()

        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist.')
        
        if(not user.organization):
            if(user.role == 'Admin'):
                return Response(f'There are no organizations for user #{user_id} yet. Create one!')
            else:
                return Response(f'There are no organizations for user #{user_id} yet.')
        
        user_org = Organization.objects.filter(members=user).first()
        serializer = self.get_serializer(user_org)
        return Response(serializer.data)
    



    
    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'organizations/<pk>'
        organization_id = self.kwargs.get('pk')
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org = Organization.objects.filter(id=organization_id).first()
        
        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist.')
        
        elif(not org):
            raise PermissionDenied(f'Organization #{organization_id} does not exist.')
        
        elif(user.organization != org):
            if(user.role == 'Admin'):
                raise PermissionDenied(f'Organization \'{org.name}\' does not belong to user \'{user.username}\'.')
            raise PermissionDenied(f'Organization \'{org.name}\' does not have a member \'{user.username}\'.')

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
        
        org = Organization.objects.filter(members=user)

        if(org.filter(name=name , location=location , organization_type=org_type , established_date=est_date , contact_email=contact_email)):
            raise serializers.ValidationError(f'This organization already exists.')
            
        if(org.filter(contact_email=contact_email)):
            raise serializers.ValidationError(f'This contact email already exists.')
        
        if(org.filter(name=name , location=location)):
            raise serializers.ValidationError(f'There is another organization with the same name in {location}.')
        
        organization = serializer.save()
        user.organization = organization
        user.save(update_fields=['organization'])

        # request invited users to organization
        org = Organization.objects.filter(id=organization.id , members = user).first()
        invited_users = serializer.validated_data.get('invite_user' , [])
        
        if(org):
            if(invited_users):
                for inv_user in invited_users:
                    receiver_notification = f'Organization \'{org}\' is interested in engaging you for a position.'
                    sender_notification = f'Organization \'{org}\' invited \'{inv_user}\' to join the company.'
                    context = {'request': request , 'receiver_notification': receiver_notification , 'sender_notification': sender_notification , \
                               'sender_organization': org , 'receiver_user': inv_user , 'reason': 'org_invites_user'}
                    data = {}
                    # ORGANIZATION -> USER
                    inv = InvitationSerializer(data=data , context=context)
                    inv.is_valid(raise_exception=True)
                    inv.save()
            
        return Response(serializer.data , status=201)
    
    




    def update(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>
        org_id = self.kwargs.get('pk')
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        org = Organization.objects.filter(members=user)

        if(not user or (user and user.organization != org.first())):
            return Response(f'Organization was not updated!' , status=403)
        
        
        serializer = self.get_serializer(Organization.objects.get(id=org_id) , data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data.get('name')
        location = serializer.validated_data.get('location')
        org_type = serializer.validated_data.get('organization_type')
        est_date = serializer.validated_data.get('established_date')
        contact_email = serializer.validated_data.get('contact_email')
        
        

        
        if(org.filter(name=name , location=location , organization_type=org_type , established_date=est_date , contact_email=contact_email) \
               .exclude(id=serializer.instance.id)):
            raise serializers.ValidationError(f'This organization already exists.')
            
        if(org.filter(contact_email=contact_email).exclude(id=serializer.instance.id) and Organization.objects.get(id=org_id).contact_email != contact_email):
            raise serializers.ValidationError(f'This contact email already exists.')
        
        if(org.filter(name=name , location=location).exclude(id=serializer.instance.id)):
            raise serializers.ValidationError(f'There is another organization with the same name in {location}.')
        

        # request invited users to organization
        org = Organization.objects.filter(members = user , id = self.kwargs.get('pk')).first()
        invited_users = serializer.validated_data.get('invite_user' , [])
        
        if(org):
            deleted_users = serializer.validated_data.get('fire_user' , [])
            if(invited_users):
                for inv_user in invited_users:
                    receiver_notification = f'Organization \'{org}\' is interested in engaging you for a position.'
                    sender_notification = f'Organization \'{org}\' invited \'{inv_user}\' to join the company.'
                    context = {'request': request , 'receiver_notification': receiver_notification , 'sender_notification': sender_notification , \
                               'sender_organization': org , 'receiver_user': inv_user , 'reason': 'org_invites_user'}
                    data = {}
                    # ORGANIZATION -> USER
                    inv = InvitationSerializer(data=data , context=context)
                    inv.is_valid(raise_exception=True)
                    inv.save()
        
            
            elif(deleted_users):
                org.members.remove(*deleted_users)
                for del_user in deleted_users:
                    receiver_notification = f'Organization \'{org}\' fired you from the company.'
                    sender_notification = f'Organization \'{org}\' fired \'{del_user}\' from the company.'
                    context = {'request': request , 'receiver_notification': receiver_notification , 'sender_notification': sender_notification , \
                               'sender_organization': org , 'receiver_user': del_user , 'reason': 'org_fires_user'}
                    data = {}
                    # ORGANIZATION -> USER
                    inv = InvitationSerializer(data=data , context=context)
                    inv.is_valid(raise_exception=True)
                    inv.save()



        serializer.save()
        updated_org = serializer.instance
        refreshed_serializer = self.get_serializer(updated_org)
        return Response(refreshed_serializer.data , status=200)






    def destroy(self , *args , **kwargs):
        org_number = self.kwargs.get('pk')
        org = Organization.objects.filter(id=org_number).first()
        
        if(not org):
            raise ValidationError(f'Organization #{org_number} not exists.')

        org.delete()
        return Response(f'Organization #{org_number} deleted successfully.' , status=204)













class BinViewSet(viewsets.ModelViewSet):
    serializer_class = BinSerializer
    permission_classes = [RoleBasedPermission]
    
    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()

        if(user and organization and user.organization):
            return Bin.objects.filter(organization_id=organization.id)
        return Bin.objects.none()
    



    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'bins/'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()

        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist. Bin can not be created!')
        
        if(not organization):
            raise PermissionDenied(f'Organization #{org_id} does not exist. Bin can not be created!')
        
        elif(not user.organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong to any organization yet')
        
        elif(user.organization != organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong in organization \'{organization.name}\'.')
        
        elif(user.role not in ['Admin' , 'Manager']):
            raise PermissionDenied('Only administrators and managers are authorized to create or modify bins.')
        
        elif(organization.bins.count() == 0 and user.role in ['Admin' , 'Manager']):
            return Response(f'There are no bins for \'{organization.name}\' organization yet. Create one!')
        
        return super().list(request , *args , **kwargs)
    



    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'bins/<pk>'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()
        bin_id = self.kwargs.get('pk')
        

        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist.')
        
        if(not organization):
            raise PermissionDenied(f'Organization #{org_id} does not exist.')
        
        elif(not user.organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong to any organization yet.')
        
        elif(user.organization != organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong in organization \'{organization.name}\'.')

        org_bin = organization.bins.filter(id = bin_id).first()
        if(not org_bin):
            raise PermissionDenied(f'Bin #{bin_id} does not belong to organization \'{organization.name}\'.')
        
        return super().retrieve(request , *args , **kwargs)
    




    def create(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/bins/
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        organization = Organization.objects.filter(id=org_id).first()


        if(not user or not organization or not user.organization):
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

        if(not user or not organization or (user and organization and not user.organization) or not organization.bins.filter(id = bin_id).first()):
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
    

    def destroy(self , *args , **kwargs):
        org_id = self.kwargs.get('organization_pk')
        if(not org_id):
            raise ValidationError(f'Organization {org_id} does not exist.')
        
        organization = Organization.objects.filter(id=org_id).first()
        bin_id = self.kwargs.get('pk')
        bin = organization.bins.filter(id = bin_id).first()

        if(not bin):
            raise ValidationError(f'Bin #{bin_id} does not exist.')

        bin.delete() 
        return Response(f'Bin #{self.kwargs.get('pk')} removed successfully.' , status=204)
    


    












class TruckViewSet(viewsets.ModelViewSet):
    serializer_class = TruckSerializer
    permission_classes = [AllowActions]

    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()

        if(user and organization and user.organization):
            return Truck.objects.filter(organization_id=organization.id)
        return Truck.objects.none()
    

    def get_permissions(self):
        return [AllowActions()]



    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'trucks/'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()

        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist. Truck can not be created!')
        
        if(not organization):
            raise PermissionDenied(f'Organization #{org_id} does not exist. Truck can not be created!')
        
        elif(not user.organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong to any organization yet.')
        
        elif(user.organization != organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong in organization \'{organization.name}\'.')

        elif(user.role not in ['Admin' , 'Manager']):
            return Response('Only administrators and managers are authorized to create or modify bins.' , status=403)
        
        elif(organization.trucks.count() == 0 and user.role in ['Admin' , 'Manager']):
            return Response(f'There are no trucks for \'{organization.name}\' organization yet. Create one!')
        
        return super().list(request , *args , **kwargs)
    





    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'trucks/<pk>'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()
        truck_id = self.kwargs.get('pk')
        
        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist.')
        
        if(not organization):
            raise PermissionDenied(f'Organization #{org_id} does not exist.')
        
        elif(not user.organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong to any organization yet.')
        
        elif(user.organization != organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong in organization \'{organization.name}\'.')

        org_truck = organization.trucks.filter(id = truck_id).first()
        if(not org_truck):
            raise PermissionDenied(f'Truck #{truck_id} does not belong to organization \'{organization.name}\'.')
        
        return super().retrieve(request , *args , **kwargs)
    

    



    def create(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/trucks/
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        organization = Organization.objects.filter(id=org_id).first()

        if(not user or not organization or not user.organization):
            return Response(f'Truck was not created!' , status=403)
                
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

        if(not user or not organization or (user and organization and not user.organization) or not organization.trucks.filter(id = truck_id).first()):
            return Response(f'Truck was not updated!' , status=403)
                

        serializer = self.get_serializer(organization.trucks.filter(id = truck_id).first() , data=request.data) 
        serializer.is_valid(raise_exception=True)
        truck = serializer.save(organization = organization)

        if(truck):
            if((truck.current_load / truck.capacity) * 100 >= 80 and truck.status == 'Available'):
                truck.status = 'Unloading'
                truck.message = '🚛⬇️The truck is heading to the waste transfer station to unload.'
                truck.save()

                pickup_request = PickUpRequest.objects.filter(organization=organization , status='On the way' , truck=truck_id)

                if(pickup_request.exists()):
                    raise PermissionDenied(f'Truck can not be unload, because it\'s on the way to pickup \'{pickup_request.first().bin}\' bin')

                else:
                    schedule , _= IntervalSchedule.objects.get_or_create(every=5 , period=IntervalSchedule.SECONDS)
            
                    PeriodicTask.objects.create(interval=schedule , name=f"unload_truck{truck.id}-for-org-{organization.id}" , \
                                            task="smart_waste_app.tasks.create_unload_truck" , args=json.dumps([truck.id]))

        return Response(serializer.data , status=200)
    



    def perform_create(self , serializer):
        organization = Organization.objects.get(id=self.kwargs.get('organization_pk'))
        serializer.save(organization=organization)



    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['organization_pk'] = self.kwargs.get('organization_pk')
        return context



    def destroy(self , *args , **kwargs):
        org_id = self.kwargs.get('organization_pk')
        if(not org_id):
            raise ValidationError(f'Organization {org_id} does not exist.')
        
        organization = Organization.objects.filter(id=org_id).first()
        truck_id = self.kwargs.get('pk')
        truck = organization.trucks.filter(id = truck_id).first()

        if(not truck):
            raise ValidationError(f'Truck #{truck_id} does not exist.')

        truck.delete() 
        return Response(f'Truck #{self.kwargs.get('pk')} removed successfully.' , status=204)
    











class PickUpRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PickUpRequestSerializer
    permission_classes = [AllowActions]

    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()

        if(user and organization and user.organization):
            return PickUpRequest.objects.filter(organization=organization)
        return PickUpRequest.objects.none()




    def get_permissions(self):
        return [AllowActions()]
    



    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'pickuprequests/'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()

        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist. Pickup request can not be created!')
        
        if(not organization):
            raise PermissionDenied(f'Organization #{org_id} does not exist. Pickup request can not be created!')
        
        elif(not user.organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong to any organization yet. Pickup request can not be created!')
        
        elif(user.organization != organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong in organization \'{organization.name}\'. Pickup request can not be created!')
        
        if(user.role not in ['Admin' , 'Manager']):
            raise PermissionDenied('Only administrators and managers are authorized to create or modify bins.')
        
        trucks = Truck.objects.filter(organization=organization).exists()
        bins = Bin.objects.filter(organization=organization).exists()
        
        if(not trucks or not bins):
            var = ''
            if(not trucks and not bins):
                var = 'no trucks nor bins'
            elif(not trucks):
                var = 'no trucks'
            elif(not bins):
                var = 'no bins'
            raise PermissionDenied(f'There are {var} for \'{organization.name}\' organization yet. Pickup request can not be created!')
        
        if(organization.org_pickup_requests.count() == 0 and user.role in ['Admin' , 'Manager']):
            return Response(f'There are no pickup requests for \'{organization.name}\' organization yet. Create one!')
        
                 
        return super().list(request , *args , **kwargs)
       






    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'pickuprequests/<pk>'
        user_id = self.kwargs.get('user_pk')
        org_id = self.kwargs.get('organization_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        organization = Organization.objects.filter(id=org_id).first()
        pickup_request_id = self.kwargs.get('pk')
        

        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist.')
        
        if(not organization):
            raise PermissionDenied(f'Organization #{org_id} does not exist.')
        
        elif(not user.organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong to any organization yet.')
        
        elif(user.organization != organization):
            raise PermissionDenied(f'User \'{user.username}\' does not belong in organization \'{organization.name}\'.')

        org_pickup_request = organization.org_pickup_requests.filter(id = pickup_request_id).first()
        if(not org_pickup_request):
            raise PermissionDenied(f'Pickup request #{pickup_request_id} does not belong to organization \'{organization.name}\'.')
        
        return super().retrieve(request , *args , **kwargs)
    



    def create(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/pickuprequests/
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        organization = Organization.objects.filter(id=org_id).first()
        trucks = Truck.objects.filter(organization=organization).exists()
        bins = Bin.objects.filter(organization=organization).exists()

        if(not user or not organization or not user.organization) or not trucks or not bins:
            return Response(f'Pickup request was not created!' , status=403)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message = self.perform_create(serializer)
        
        return Response(message , status=201)






    def update(self , request , *args , **kwargs): # /users/<pk>/organizations/<pk>/pickuprequests/<pk>
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        org_id = self.kwargs.get('organization_pk')
        organization = Organization.objects.filter(id=org_id).first()
        pickuprequest_id = self.kwargs.get('pk')

        if(not user or not organization or (user and organization and not user.organization) or not organization.org_pickup_requests.filter(id = pickuprequest_id).first()):
            return Response(f'Pickup request was not updated!' , status=403)
            
        serializer = self.get_serializer(organization.org_pickup_requests.get(id = pickuprequest_id) , data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization = organization)
        return Response(serializer.data , status=200)
    


    def perform_create(self , serializer):
        organization = Organization.objects.get(id=self.kwargs.get('organization_pk'))
        truck = serializer.validated_data.get('truck')
        bin = serializer.validated_data.get('bin')
        auto_assign_all = serializer.validated_data.get('auto_assign_all')
        auto_assign_truck = serializer.validated_data.get('auto_assign_truck')
        now = serializer.validated_data.get('now')
        scheduled_at = serializer.validated_data.get('scheduled_at')


        if((truck and bin and not auto_assign_all and not auto_assign_truck) or (auto_assign_truck and bin) or auto_assign_all):
            if(not auto_assign_all and bin.current_fill_level == 0):
                return f'{bin.bin_type} bin at \'{bin.location}\' is already empty.'
            
            if(now and not auto_assign_all and not auto_assign_truck):
                if(bin.threshold_level < 50):
                    return f'{bin.bin_type} bin at {bin.location} has not exceeded the threshold level to require emptying.'
                
                if(truck.status == 'Unloading'):
                    return f'{truck} truck can\'t pickup right now, because is heading to the waste transfer station to unload.'
            
                pickup_request = PickUpRequest.objects.filter(organization=organization , status__in = ['On the way' , 'Pending'] , truck=truck.id)
                if(pickup_request.exists()):
                    return f'The pickup request cannot be processed right now, because {truck.license_plate} is already on route.'
                
            if(not auto_assign_all):
                pickup = PickUpRequest.objects.filter(organization=organization , status__in = ['On the way' , 'Pending'] , bin=bin.id)
                if(pickup.exists()):
                    for p in pickup:
                        if(p.scheduled_at):
                            if(p.scheduled_at and (p.bin == bin or p.truck == truck)):
                                if(scheduled_at <= p.scheduled_at + timedelta(minutes=2) and scheduled_at >= p.scheduled_at - timedelta(minutes=2)):
                                    return 'At this time, another pickup request has already been assigned.'
                        else: 
                            return f'The pickup request cannot be processed as there is already an active pickup request for {bin} bin.'
            
            if(not auto_assign_truck and not auto_assign_all):
                if(truck.current_load + bin.current_fill_level > truck.capacity):
                    if(not auto_assign_all and not auto_assign_truck):
                        return f'Truck \'{truck.license_plate}\' cannot pickup the {str(bin.bin_type).lower()} bin at \'{bin.location}\', due to full load. Empty the truck\'s load or search for another bin.'
                

            schedule , _= IntervalSchedule.objects.get_or_create(every=5 , period=IntervalSchedule.SECONDS)
            

            if(scheduled_at):
                scheduled_pickup_request_list = PickUpRequest.objects.filter(status__in = ['Pending' , 'On the way'] , scheduled_at__isnull=False)
                
                for sch in scheduled_pickup_request_list:
                    if(not auto_assign_all and not auto_assign_truck):
                        if(sch.bin == bin or sch.truck == truck):   
                            if(scheduled_at <= sch.scheduled_at + timedelta(minutes=2) and scheduled_at >= sch.scheduled_at - timedelta(minutes=2)):
                                raise ValidationError('At this time, another pickup request has already been assigned.')


            if(PickUpRequest.objects.filter(status='Pending' , auto_assign_all=True).exists()):
                    raise ValidationError('Currently, no trucks are available, as the system is processing assignments to determine which vehicles will be dispatched for pending pickup requests.')


            if(not auto_assign_all):
                pickup_request = serializer.save(organization=organization)                    

                if((not auto_assign_truck and pickup_request.truck.status == 'Available') or auto_assign_truck):
                    PeriodicTask.objects.create(interval=schedule , name=f"pickup-task{pickup_request.id}-for-org-{organization.id}" , \
                                            task="smart_waste_app.tasks.create_pickup_request" , args=json.dumps([organization.id , None]))
                    return f'Pickup request #{pickup_request.id} created successfully.'
            

            bins = list(Bin.objects.filter(organization=self.kwargs.get('organization_pk')).exclude(current_fill_level = 0 , threshold_level__lt = 0.5))
            trucks = list(Truck.objects.filter(organization=self.kwargs.get('organization_pk') , status='Available').all())

            if(len(bins) == 0):
                raise ValidationError('There are no bins containing any load available for collection by a truck.')
            
            if(len(trucks) == 0):
                raise ValidationError('There are no trucks available for pickup.')

            truck_can_pickup = True
            for truck in trucks:
                for bin in bins:
                    if(truck.current_load + bin.current_fill_level > truck.capacity):
                        truck_can_pickup = False
                    else:
                        truck_can_pickup = True
                if(truck_can_pickup):
                    break
            
            if(not truck_can_pickup):
                raise ValidationError('No truck is currently available to collect any bin, as the load exceeds its capacity.')
                    
                    
            bins_number = Bin.objects.filter(organization=organization , current_fill_level__gt = 0).count()
            pickup_requests_created = []

            pickup_request_ids_list = []
            for i in range(bins_number):
                serializer = PickUpRequestSerializer(data=self.request.data) # create new pickup request (with new id)
                serializer.is_valid(raise_exception=True)
                pickup_request = serializer.save(organization=organization)
                pickup_requests_created.append(pickup_request.id)
                pickup_request_ids_list.append(pickup_request.id)

            PeriodicTask.objects.create(interval=schedule , name=f"auto_assign_all_pickup-task{pickup_request.id}-for-org-{organization.id}" , \
                                    task="smart_waste_app.tasks.create_pickup_request" , args=json.dumps([organization.id , pickup_request_ids_list]))            
            
            pickup_requests_created = ', '.join(f'#{ids}' for ids in pickup_requests_created)
            s = 's' if(bins_number > 1) else ''
            return f'Pickup request{s} {pickup_requests_created} created successfully.'






    
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
    


    def destroy(self , *args , **kwargs):
        org_id = self.kwargs.get('organization_pk')
        if(not org_id):
            raise ValidationError(f'Organization {org_id} does not exist.')
        
        organization = Organization.objects.filter(id=org_id).first()
        pickup_request_id = self.kwargs.get('pk')
        pickup_request = organization.org_pickup_requests.filter(id = pickup_request_id).first()

        if(not pickup_request):
            raise ValidationError(f'Pickup request #{pickup_request_id} does not exist.')

        pickup_request.delete() 
        return Response(f'Pickup request #{self.kwargs.get('pk')} removed successfully.' , status=204)
    
    











class BaseInvitationViewSet(mixins.ListModelMixin , mixins.RetrieveModelMixin , mixins.UpdateModelMixin , viewsets.GenericViewSet):
    serializer_class = InvitationSerializer
    permission_classes = [AllowActions]



    def get_permissions(self):
        return [AllowActions()]



    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'invitations/'
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        
        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist.')

        if(self.request):
            if('organizations' in self.request.path):
                organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()
                
                if(not organization):
                    raise PermissionDenied(f'Organization #{self.kwargs.get('organization_pk')} does not exist.')

                if(not user.organization):
                     raise PermissionDenied(f'User has no organizations.')

                
                if(request and 'sent-invitations' in request.path):
                    if(organization.sender_org_invitations.count() == 0):
                        raise PermissionDenied(f'There are no sent-invitations for organization \'{user.organization.name}\' yet.')
                
                if(request and 'received-invitations' in request.path):
                    if(organization.receiver_org_invitations.count() == 0):
                        raise PermissionDenied(f'There are no received-invitations for organization \'{user.organization.name}\' yet.')

            else:
                if(request and 'sent-invitations' in request.path):
                    if(user.sender_user_invitations.count() == 0):
                        raise PermissionDenied(f'There are no sent-invitations for user \'{user.username}\' yet.')
                
                if(request and 'received-invitations' in request.path):
                    if(user.receiver_user_invitations.count() == 0):
                        raise PermissionDenied(f'There are no received-invitations for user \'{user.username}\' yet.')
                
        return super().list(request , *args , **kwargs)







    def retrieve(self , request , *args , **kwargs): # I use 'retrieve' function, because I call [GET] on 'invitations/<pk>'
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
                

        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist.')
        
        if(request):
            if('organizations' in self.request.path):
                org_id = self.kwargs.get('organization_pk')
                organization = Organization.objects.filter(id=org_id).first()
                
                if(not organization):
                    raise PermissionDenied(f'Organization #{org_id} does not exist.')
            
                elif(not user.organization):
                    raise PermissionDenied(f'\'{user.username}\' does not belong to any organization yet.')
                
                elif(user.organization != organization):
                    raise PermissionDenied(f'\'{user.username}\' does not belong in organization \'{organization.name}\'.')

                if(request and 'received-invitations' in request.path):
                    invitation = Invitation.objects.filter(receiver_organization=organization , id = self.kwargs.get('pk')).exists()
                
                    if(not invitation):
                        raise PermissionDenied(f'Received-invitation #{self.kwargs.get('pk')} for organization \'{organization.name}\' does not exist.')
                    
                if(request and 'sent-invitations' in request.path):
                    invitation = Invitation.objects.filter(sender_organization=organization , id = self.kwargs.get('pk')).exists()
                
                    if(not invitation):
                        raise PermissionDenied(f'Sent-invitation #{self.kwargs.get('pk')} for organization \'{organization.name}\' does not exist.')
                
            else:
                if(request and 'received-invitations' in request.path):
                    invitation = Invitation.objects.filter(receiver_user=user , id = self.kwargs.get('pk')).exists()
            
                    if(not invitation):
                        raise PermissionDenied(f'Received-invitation #{self.kwargs.get('pk')} for user \'{user.username}\' does not exist.')
                
                if(request and 'sent-invitations' in request.path):
                    invitation = Invitation.objects.filter(sender_user=user , id = self.kwargs.get('pk')).exists()
            
                    if(not invitation):
                        raise PermissionDenied(f'Sent-invitation #{self.kwargs.get('pk')} for user \'{user.username}\' does not exist.')
            

        return super().retrieve(request , *args , **kwargs)
        




    def get_serializer_context(self , *args , **kwargs):
        context = super().get_serializer_context()
        context['user_id'] = self.kwargs.get('user_pk')
        context['organization_id'] = self.kwargs.get('organization_pk')
        return context


    













class UserSentInvitationsViewSet(BaseInvitationViewSet , mixins.CreateModelMixin):
    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()

        if(user):
            user_inv = Invitation.objects.filter(sender_user=user)
            if(user_inv.exists()):
                return user_inv
            
        return Invitation.objects.none()
    


    def perform_create(self, serializer):
        selected_id = serializer.initial_data.get('select')
        invitation_id = Invitation.objects.filter(id=selected_id).first().id
        if(invitation_id):
            serializer.save(invitation=invitation_id)


    def get_serializer_context(self , *args , **kwargs):
        context = super().get_serializer_context()
        context['cancel'] = self.request.data.get('cancel')
        return context
    







class UserReceivedInvitationsViewSet(BaseInvitationViewSet , mixins.CreateModelMixin , mixins.DestroyModelMixin):
    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        
        if(user):
            user_inv = Invitation.objects.filter(receiver_user=user)

            if(user_inv.exists()):
                return user_inv
            
        return Invitation.objects.none()
    

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitations = serializer.save()

        serializer = InvitationSerializer(invitations , context=self.get_serializer_context())
        return Response(serializer.data , status=status.HTTP_200_OK)
    

    def destroy(self , *args , **kwargs):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        
        if(not user):
            raise ValidationError('User not found.')
        invitation = Invitation.objects.filter(id=self.kwargs.get('pk'))

        if(not invitation):
            raise ValidationError(f'Received-invitation #{self.kwargs.get('pk')} does not exist.')

        invitation.delete() 
        return Response(f'Received-invitation #{self.kwargs.get('pk')} removed successfully.' , status=204)
    








class OrganizationSentInvitationsViewSet(BaseInvitationViewSet , mixins.CreateModelMixin):
    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        
        if(user):
            organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()
            if(organization):
                return Invitation.objects.filter(sender_organization=organization)
            
        return Invitation.objects.none()
    


    def perform_create(self, serializer):
        selected_id = serializer.initial_data.get('select')
        invitation_id = Invitation.objects.filter(id=selected_id).first().id
        if(invitation_id):
            serializer.save(invitation=invitation_id)


    def get_serializer_context(self , *args , **kwargs):
        context = super().get_serializer_context()
        context['cancel'] = self.request.data.get('cancel')
        return context









class OrganizationReceivedInvitationsViewSet(BaseInvitationViewSet , mixins.CreateModelMixin , mixins.DestroyModelMixin):
    def get_queryset(self):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()

        if(user):
            organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()
            if(organization):
                return Invitation.objects.filter(receiver_organization=organization)
            
        return Invitation.objects.none()


    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitations = serializer.save()

        serializer = InvitationSerializer(invitations , context=self.get_serializer_context())
        return Response(serializer.data , status=status.HTTP_200_OK)
    


    def destroy(self , *args , **kwargs):
        user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
        
        if(not user):
            raise ValidationError('User not found.')
        invitation = Invitation.objects.filter(id=self.kwargs.get('pk'))

        if(not invitation):
            raise ValidationError(f'Received-invitation #{self.kwargs.get('pk')} does not exist.')

        invitation.delete() 
        return Response(f'Received-invitation #{self.kwargs.get('pk')} removed successfully.' , status=204)








    




class ReplyViewSet(viewsets.ModelViewSet):
    serializer_class = ReplySerializer
    permission_classes = [AllowActions]



    def get_permissions(self):
        return [AllowActions()]
    



    def get_queryset(self):
        if('organizations' in self.request.path):
            user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
            org = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()
            if(user and org):
                return Reply.objects.filter(receiver_organization=org)
        
        elif('organizations' not in self.request.path):
            user = CustomUser.objects.filter(id=self.kwargs.get('user_pk')).first()
            if(user):
                return Reply.objects.filter(receiver_user=user)

        return Reply.objects.none()

    






    def list(self , request , *args , **kwargs): # I use 'list' function, because I call [GET] on 'replies/'
        user_id = self.kwargs.get('user_pk')
        user = CustomUser.objects.filter(id=user_id).first()
        
        if(not user):
            raise PermissionDenied(f'User #{user_id} does not exist.')

        if(self.request):
            if('organizations' in self.request.path):
                organization = Organization.objects.filter(id=self.kwargs.get('organization_pk')).first()
                
                if(not organization):
                    raise PermissionDenied(f'Organization #{self.kwargs.get('organization_pk')} does not exist.')

                if(not user.organization):
                     raise PermissionDenied(f'User has no organizations.')

                
                if(request and 'replies' in request.path):
                    if(organization.receiver_org_replies.count() == 0):
                        raise PermissionDenied(f'There are no replies for organization \'{user.organization.name}\' yet.')

            else:
                if(request and 'replies' in request.path):
                    if(user.receiver_user_replies.count() == 0):
                        raise PermissionDenied(f'There are no replies for user \'{user.username}\' yet.')
                
        return super().list(request , *args , **kwargs)
    







    def get_serializer_context(self , *args , **kwargs):
        context = super().get_serializer_context()
        context['user_id'] = self.kwargs.get('user_pk')
        context['organization_id'] = self.kwargs.get('organization_pk')
        return context
    





    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data , context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        selected_reply_id = serializer.initial_data.get('select') # get id of Reply (from select)

        invitation_id = Reply.objects.filter(id=selected_reply_id).first().invitation.id
        reply = serializer.save(invitation=invitation_id)
        response_serializer = ReplySerializer(reply , many=True , context=self.get_serializer_context())

        return Response(response_serializer.data , status=status.HTTP_201_CREATED)
