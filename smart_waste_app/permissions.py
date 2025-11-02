from rest_framework.permissions import BasePermission
from .models import CustomUser , Reply , Organization , Invitation , PickUpRequest , Truck
from django.db.models import Q



class RoleBasedPermission(BasePermission):
    def has_permission(self , request , view):
        if(request.method == 'GET'):
            return True
        
        view_name = view.__class__.__name__

        user_id = view.kwargs.get('user_pk')    
        user = CustomUser.objects.filter(id = user_id).first()
        
        if(view_name == 'OrganizationViewSet'):
            return (user and user.role == 'Admin')
        
        if(view_name in ['BinViewSet' , 'TruckViewSet' , 'PickUpRequestViewSet']):
            return (user and user.role in ['Admin' , 'Manager'])





class AllowActions(BasePermission):
    def has_permission(self , request , view):
        from smart_waste_app.views import OrganizationViewSet , CustomUserViewSet , ReplyViewSet , BaseInvitationViewSet , PickUpRequestViewSet , TruckViewSet

        # action permissions for organization viewset
        if(isinstance(view , OrganizationViewSet)):
            user = CustomUser.objects.filter(id=view.kwargs.get('user_pk')).first()
            if(user.role == 'Admin' and user.organization):
                if(request.method == 'POST'):
                    return False
                return True
                
            if(user.role != 'Admin' and request.method in ['POST' , 'PUT' , 'PATCH' , 'DELETE']):
                return False
            

        # action permissions for customuser viewset
        if(isinstance(view , CustomUserViewSet)):
            user = CustomUser.objects.filter(id=view.kwargs.get('pk')).first()
            if(not user and request.method in ['PUT' , 'PATCH' , 'DELETE']):
                return False
            

        # action permissions for reply viewset
        if(isinstance(view , ReplyViewSet)):
            user = CustomUser.objects.filter(id=view.kwargs.get('user_pk')).first()
            if('organizations' not in request.path):
                user_invitations = Invitation.objects.filter(sender_user=user).values_list('id' , flat=True)
                if(user and not Reply.objects.filter(invitation__id__in = user_invitations , final_decision='Pending').exists() and request.method in ['POST' , 'PUT' , 'PATCH' , 'DELETE']):
                    return False
                
            elif('organizations' in request.path):
                org = Organization.objects.filter(members=user).first()
                org_invitations = Invitation.objects.filter(sender_organization=org).values_list('id' , flat=True)
                if(user and org and not Reply.objects.filter(invitation__id__in = org_invitations , final_decision='Pending').exists() and request.method in ['POST' , 'PUT' , 'PATCH' , 'DELETE']):
                    return False
                

        # action permissions for baseinvitation viewset
        if(isinstance(view , BaseInvitationViewSet)):
            user = CustomUser.objects.filter(id=view.kwargs.get('user_pk')).first()
            
            if('organizations' not in request.path):
                if(user and not Invitation.objects.filter(id=view.kwargs.get('pk') , status='Pending').first() and request.method in ['PUT' , 'PATCH' , 'DELETE']):
                    return False
            
            elif('organizations' in request.path):
                org = Organization.objects.filter(members=user).first()
                if(user and org and not Invitation.objects.filter(id=view.kwargs.get('pk') , status='Pending').first() and request.method in ['PUT' , 'PATCH' , 'DELETE']):
                    return False

            if('received-invitations' in request.path):
                if('organizations' not in request.path):                    
                    if(user and not Invitation.objects.filter(receiver_user=user , status='Pending').exists() and request.method in ['POST' , 'PUT' , 'PATCH' , 'DELETE']):
                        return False
                    
                elif('organizations' in request.path):
                    org = Organization.objects.filter(members=user).first()

                    if(user and org and not Invitation.objects.filter(receiver_organization=org , status='Pending').exists() and request.method in ['POST' , 'PUT' , 'PATCH' , 'DELETE']):
                        return False
                    
            elif('sent-invitations' in request.path):
                if('organizations' not in request.path):                    
                    if(user and not Invitation.objects.filter(sender_user=user , status='Pending').exists() and request.method in ['POST' , 'PUT' , 'PATCH' , 'DELETE']):
                        return False
                    
                elif('organizations' in request.path):
                    org = Organization.objects.filter(members=user).first()
                    
                    if(user and org and not Invitation.objects.filter(sender_organization=org , status='Pending').exists() and request.method in ['POST' , 'PUT' , 'PATCH' , 'DELETE']):
                        return False


        # action permissions for pickup request viewset
        if(isinstance(view , PickUpRequestViewSet)):
            user = CustomUser.objects.filter(id=view.kwargs.get('user_pk')).first()
            org = Organization.objects.filter(members=user).first()
            pickup_id = view.kwargs.get('pk')

            if(user and org and PickUpRequest.objects.filter(id=pickup_id , organization = org , status__in = ['Completed' , 'Aborted']) and request.method in ['PUT' , 'PATCH']):
                return False

            if(user and org and not PickUpRequest.objects.filter(id=pickup_id).exists() and request.method in ['PUT' , 'PATCH' , 'DELETE']):
                return False


        # action permissions for pickup request viewset
        if(isinstance(view , TruckViewSet)):
            user = CustomUser.objects.filter(id=view.kwargs.get('user_pk')).first()
            org = Organization.objects.filter(members=user).first()
            truck_id = view.kwargs.get('pk')

            if(user and org and Truck.objects.filter(organization = org) and request.method in ['PUT' , 'PATCH']):
                return False
            
            if(user and org and not Truck.objects.filter(id=truck_id) and request.method in ['PUT' , 'PATCH' , 'DELETE']):
                return False
                        
        return True
        