from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator , MaxValueValidator
from django.utils import timezone
import string , random
from smart_waste_management_system import settings
from rest_framework.exceptions import ValidationError




def local_time():
    return timezone.now()



class Organization(models.Model):
    organization_type = [
                         ('Municipality' , 'Municipality') , 
                         ('Private Company' , 'Private Company')
                        ]
    
    locations = [
                    ('Katerini', 'Katerini'),
                    ('Thessaloniki', 'Thessaloniki'),
                    ('Kavala', 'Kavala'),
                    ('Serres', 'Serres'),
                    ('Drama', 'Drama'),
                    ('Kastoria', 'Kastoria'),
                    ('Florina', 'Florina'),
                    ('Edessa', 'Edessa'),
                    ('Naousa', 'Naousa'),
                    ('Kozani', 'Kozani'),
                    ('Grevena', 'Grevena'),
                    ('Komotini', 'Komotini'),
                    ('Xanthi', 'Xanthi'),
                    ('Alexandroupoli', 'Alexandroupoli'),
                    ('Orestiada', 'Orestiada'),
                    ('Larisa', 'Larisa'),
                    ('Volos', 'Volos'),
                    ('Trikala', 'Trikala'),
                    ('Karditsa', 'Karditsa'),
                    ('Ioannina', 'Ioannina'),
                    ('Arta', 'Arta'),
                    ('Preveza', 'Preveza'),
                    ('Igoumenitsa', 'Igoumenitsa'),
                    ('Athina', 'Athina'),
                    ('Lamia', 'Lamia'),
                    ('Chalkida', 'Chalkida'),
                    ('Thiva', 'Thiva'),
                    ('Patra', 'Patra'),
                    ('Kalamata', 'Kalamata'),
                    ('Tripoli', 'Tripoli'),
                    ('Sparti', 'Sparti'),
                    ('Nafplio', 'Nafplio'),
                    ('Corinth', 'Corinth'),
                    ('Megara', 'Megara'),
                    ('Irakleio', 'Irakleio'),
                    ('Chania', 'Chania'),
                    ('Rethymno', 'Rethymno'),
                    ('Agios Nikolaos', 'Agios Nikolaos'),
                    ('Sitia', 'Sitia')
                ]

    
    name = models.CharField(max_length=50 , blank=False , null=False)
    location = models.CharField(max_length=60 , blank=False , null=False , choices=locations)
    contact_email = models.EmailField(blank=False , null=False)
    organization_type = models.CharField(max_length=50 , choices = organization_type)
    established_date = models.DateField(blank=False , null=False)
    invite_user = models.ManyToManyField(settings.AUTH_USER_MODEL , blank=True , related_name='invited_users')
    fire_user = models.ManyToManyField(settings.AUTH_USER_MODEL , blank=True , related_name='fired_users')
    hiring  = models.BooleanField(default=False)
    notifications = models.CharField(max_length=200 , blank=True , null=True)


    def __str__(self):
        return self.name











class CustomUser(AbstractUser):
    role_type = [
                    ('Admin' , 'Admin') , 
                    ('Manager' , 'Manager') , 
                    ('Driver' , 'Driver')
                ]

    first_name = models.CharField(max_length = 40 , blank=False , null=False)
    last_name = models.CharField(max_length = 50 , blank=False , null=False)
    organization = models.ForeignKey(Organization , blank=True , null=True , related_name='members' ,  on_delete=models.SET_NULL)
    available_for_work = models.BooleanField(default=False , help_text='Administrators can skip this.')
    role = models.CharField(max_length = 10 , blank=False , null=False , choices=role_type)
    registered_on = models.DateTimeField(default=local_time)
    request_to_join = models.ManyToManyField(Organization , related_name='join_requests')
    admin_successor = models.ForeignKey(settings.AUTH_USER_MODEL , related_name='successor_users' , blank=True , null=True , on_delete=models.CASCADE)
                                        
    sumbit_resignation = models.BooleanField(default=False)
    notifications = models.CharField(max_length=200 , blank=True , null=True)

    def save(self , *args , **kwargs):
        if(self._state.adding): # True: New CustomUser , False: CustomUser already exists
            firstLastName = '_'.join([self.first_name , self.last_name])
            username = firstLastName
            count = 1
            while(CustomUser.objects.filter(username=username).exists()):
                username = firstLastName + str(count)
                count += 1
            self.username = username.lower()
        
        else:
            existing_user = CustomUser.objects.filter(id=self.pk).first()

            if(existing_user.first_name != self.first_name or existing_user.last_name != self.last_name):
                firstLastName = '_'.join([self.first_name , self.last_name])
                username = firstLastName
                count = 1
                while(CustomUser.objects.filter(username=username).exists()):
                    username = firstLastName + str(count)
                    count += 1
                self.username = username.lower()
            
        return super().save(*args , **kwargs)





    def __str__(self):
        return self.username + ' (' + self.role + ')'












class Bin(models.Model):
    bin_types = [
                    ('Organic-Bio' , 'Organic-Bio') , 
                    ('Plastic' , 'Plastic') ,
                    ('General' , 'General') , 
                    ('Glass' , 'Glass') , 
                    ('Batteries' , 'Batteries') , 
                    ('Metal' , 'Metal') ,
                    ('Recycling' , 'Recycling')
                ]
    
    organization = models.ForeignKey(Organization , related_name='bins' , blank=False , null=False , on_delete=models.CASCADE)
    location = models.CharField(max_length=60 , blank=False , null=False)
    bin_type = models.CharField(max_length=20 , choices=bin_types)
    capacity = models.IntegerField(blank=False , null=False , validators=[MinValueValidator(5) , MaxValueValidator(500)] , verbose_name='Capacity (Kg)')
    current_fill_level = models.DecimalField(max_digits=10 , decimal_places=2 , blank=False , null=False , default=0 , validators=[MinValueValidator(0)]) 
    random_current_fill_level = models.BooleanField(default=False)
    level = models.CharField(max_length=20 , blank=False , null=False , default='Empty') # Empty / Low / High / Almost full / Full
    threshold_level = models.IntegerField(blank=True , null=True) # 50%
    last_collected_at = models.DateTimeField(default=local_time)
    created_at = models.DateTimeField(default=local_time)



    def save(self , *args , **kwargs):
        self.full_clean()
            
        if(not self.pk):
            self.current_fill_level = random.randint(0 , int(self.capacity))

        else:
            if(self.random_current_fill_level):
                self.current_fill_level = random.randint(0 , int(self.capacity))
                self.random_current_fill_level = False

        self.threshold_level = (self.current_fill_level / self.capacity) * 100

        if(self.threshold_level == 0):
            self.level = 'Empty'

        elif(self.threshold_level > 0 and self.threshold_level < 30):
            self.level = 'Low'

        elif(self.threshold_level >= 30 and self.threshold_level < 70):
            self.level = 'High'

        elif(self.threshold_level >= 70 and self.threshold_level < 100):
            self.level = 'Almost full'

        elif(self.threshold_level == 100):
            self.level = 'Full'

        return super().save(*args , **kwargs)



    def clean(self):
        super().clean()
        
        if(self.current_fill_level > self.capacity and self.pk):
            raise ValidationError('Current fill level of bin must not exceed it\'s capacity.')


    def __str__(self):
        return self.bin_type + ' bin / ' + self.location
    













class Truck(models.Model):
    speed_choice = [  
                    ('Slow' , 'Slow') ,
                    ('Normal' , 'Normal') ,
                    ('Fast' , 'Fast')
                   ]

    organization = models.ForeignKey(Organization , related_name='trucks' , blank=False , null=False , on_delete=models.CASCADE)
    license_plate = models.CharField(max_length=8 , blank=False , null=False , unique=True)
    location = models.CharField(max_length=100 , blank=False , null=False)
    base_station = models.CharField(max_length=100 , blank=False , null=False)
    waste_transfer_station = models.CharField(max_length=100 , blank=False , null=False)
    capacity = models.IntegerField(blank=False , null=False , validators=[MinValueValidator(1500) , MaxValueValidator(3000)] , verbose_name='Capacity (Kg)')
    current_load = models.DecimalField(max_digits=10 , decimal_places=2 , blank=False , null=False , default=0) 
    status = models.CharField(max_length=20 , blank=False , null=False , default='Available') # Available / Unavailable / On route / Unloading / Back to base
    level = models.CharField(max_length=20 , blank=False , null=False , default='Empty') # Empty / Low / High / Almost full / Full
    speed_category = models.CharField(max_length=10 , blank=False , choices=speed_choice , null=False , default='Normal') # Slow / Normal / Fast
    speed = models.IntegerField(blank=False , null=False)     # Each truck has a specific constant speed (eg: 60km/h)
    created_at = models.DateTimeField(default=local_time)
    unloading_time = models.DateTimeField(blank=True , null=True)
    back_to_base_time = models.DateTimeField(blank=True , null=True)
    message = models.CharField(max_length=200 , default='')


    def save(self , *args , **kwargs):
        if(not self.pk):
            license_plate = ''
            for i in range(3): 
                license_plate += random.choice(string.ascii_uppercase)
            license_plate += '-'
            for i in range(4):
                license_plate += random.choice(string.digits)
            
            while(Truck.objects.filter(license_plate=license_plate).exists()):
                license_plate = ''
                for i in range(3): 
                    license_plate += random.choice(string.ascii_uppercase)
                license_plate += '-'
                for i in range(4):
                    license_plate += random.choice(string.digits)
            
            self.license_plate = license_plate

        if(self.speed_category == 'Slow'):
            self.speed = 40
        elif(self.speed_category == 'Normal'):
            self.speed = 55
        elif(self.speed_category == 'Fast'):
            self.speed = 70


        percentage = (self.current_load / self.capacity) * 100
        pickup = PickUpRequest.objects.filter(truck=self.id).exclude(status__in=['Complete' , 'Aborted'])

        if(percentage == 0):
            self.level = 'Empty'

        elif(percentage > 0 and percentage < 30):
            self.level = 'Low'

        elif(percentage >= 30 and percentage < 70):
            self.level = 'High'

        elif(percentage >= 70 and percentage < 100):
            self.level = 'Almost full'

        elif(percentage == 100):
            self.level = 'Full'
        
        if(self.level in ['Almost full' , 'Full']):
            if(pickup.exists() and pickup.first().truck):
                pickup.first().warnings = f'⚠️ Truck {pickup.first().truck.license_plate} is {self.level.lower()}. Empty the truck\'s load before next pickup.'

        return super().save(*args , **kwargs)



    def __str__(self):
        return self.license_plate + ' / ' + self.location















class PickUpRequest(models.Model):
    bin = models.ForeignKey(Bin , on_delete=models.SET_NULL , blank=True , null=True , related_name='bin_pickup_requests')
    truck = models.ForeignKey(Truck , on_delete=models.SET_NULL , blank=True , null=True , related_name='truck_pickup_requests')
    auto_assign_truck = models.BooleanField(default=True , help_text='Automatically truck selection for optimal pickup.')
    status = models.CharField(max_length=12 , blank=False , null=False , default='Pending') # Pending / On the way / Completed / Aborted / Cancelled
    urgency_level = models.CharField(max_length=15 , blank=False , null=False , default='Normal') # Normal / High / Critical / Hazardous
    organization = models.ForeignKey(Organization , on_delete=models.CASCADE , related_name='org_pickup_requests') 
    requested_at = models.DateTimeField(default=local_time)
    pickup_at = models.DateTimeField(blank=True , null=True) 
    scheduled_at = models.DateTimeField(blank=True , null=True)
    now = models.BooleanField(default=False , help_text='The pick-up will be carried out now.')
    distance = models.DecimalField(max_digits=10 , decimal_places=1 , default=-1)
    expected_time = models.DecimalField(max_digits=10 , decimal_places=1 , default=-1)
    route = models.CharField(max_length=200 , default='NULL -> NULL')
    truck_speed = models.IntegerField(default=0)
    auto_assign_all = models.BooleanField(default=False , help_text='Automatically assign all available trucks to all bins.')
    warnings = models.CharField(max_length=200 , blank=True , null=True)
    processed = models.BooleanField(default=False)
    picked_weight = models.DecimalField(max_digits=10 , decimal_places=2 , null=False , default=0)












class Invitation(models.Model):
    sender_organization = models.ForeignKey(Organization , related_name='sender_org_invitations' , on_delete=models.CASCADE , blank=True , null=True)
    receiver_organization = models.ForeignKey(Organization , related_name='receiver_org_invitations' , on_delete=models.CASCADE , blank=True , null=True)
    sender_user = models.ForeignKey(settings.AUTH_USER_MODEL , related_name='sender_user_invitations' , on_delete=models.CASCADE , blank=True , null=True)
    receiver_user = models.ForeignKey(settings.AUTH_USER_MODEL , related_name='receiver_user_invitations' , on_delete=models.CASCADE , blank=True , null=True)
    status = models.CharField(max_length=30 , blank=False , null=False , default='Pending') # Pending / Accepted / Declined / Cancelled / Aborted / Fired
    created_at = models.DateTimeField(default=local_time)
    updated_at = models.DateTimeField(default=local_time) 
    accept = models.BooleanField(default=False)
    decline = models.BooleanField(default=False)
    cancel = models.BooleanField(default=False) # when invitation is cancelled
    sender_user_notification = models.CharField(max_length=200 , blank=True , null=True)
    receiver_user_notification = models.CharField(max_length=200 , blank=True , null=True)
    sender_organization_notification = models.CharField(max_length=200 , blank=True , null=True)
    receiver_organization_notification = models.CharField(max_length=200 , blank=True , null=True)
    reason = models.CharField(max_length=30 , blank=True , null=True)


    def __str__(self):
        if(self.receiver_user_notification):
            return str(self.id) + ' - ' + str(self.receiver_user_notification)
        
        if(self.receiver_organization_notification):
            return str(self.id) + ' - ' + str(self.receiver_organization_notification)
        
        return '-'
        


    class Meta:
        ordering = ['created_at']













class Reply(models.Model):
    invitation = models.ForeignKey(Invitation , on_delete=models.CASCADE , related_name='replies')
    receiver_organization = models.ForeignKey(Organization , related_name='receiver_org_replies' , on_delete=models.CASCADE , blank=True , null=True)
    receiver_user = models.ForeignKey(settings.AUTH_USER_MODEL , related_name='receiver_user_replies' , on_delete=models.CASCADE , blank=True , null=True)
    message = models.CharField(max_length = 200 , blank=True , null=True)
    created_at = models.DateTimeField(default=local_time)
    accept = models.BooleanField(default=False)
    decline = models.BooleanField(default=False)
    final_decision = models.CharField(max_length=30 , blank=False , null=False , default='Pending') # Pending / Accepted / Declined / Aborted
    receiver_user_notification = models.CharField(max_length=200 , blank=True , null=True)
    receiver_organization_notification = models.CharField(max_length=200 , blank=True , null=True)
    


    def __str__(self):
        if(self.invitation.reason == 'user_join'):
            return str(self.id) + ' - ' + str(self.invitation.receiver_organization.name)
        
        elif(self.invitation.reason == 'org_invites_user'):
            return str(self.id) + ' - ' + str(self.invitation.receiver_user)
        
        if(self.receiver_user_notification):
            return str(self.id) + ' - ' + str(self.receiver_user_notification)
        
        if(self.receiver_organization_notification):
            return str(self.id) + ' - ' + str(self.receiver_organization_notification)
        
        return '-'
    

    class Meta:
        ordering = ['created_at']