from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator , MaxValueValidator
from django.utils import timezone
import string , random



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
    organizations = models.ManyToManyField(Organization ,related_name='users')
    role = models.CharField(max_length = 10 , blank=False , null=False , choices=role_type)

    def save(self , *args , **kwargs):
        firstLastName = '_'.join([self.first_name , self.last_name])
        username = firstLastName
        count = 1
        while(CustomUser.objects.filter(username=username).exists()):
            username = firstLastName + str(count)
            count += 1
        self.username = username.lower()
        return super().save(*args , **kwargs)










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
    
    status_choices = [
                        ('Available' , 'Available') ,
                        ('Unavailable' , 'Unavailable') ,
                        ('Under maintenance' , 'Under maintenance')
                     ]
    
    organization = models.ForeignKey(Organization , related_name='bins' , blank=False , null=False , on_delete=models.CASCADE)
    location = models.CharField(max_length=60 , blank=False , null=False)
    bin_type = models.CharField(max_length=20 , choices=bin_types)
    capacity = models.IntegerField(blank=False , null=False , validators=[MinValueValidator(0) , MaxValueValidator(200)] , verbose_name='Capacity (Kg)')
    current_fill_level = models.DecimalField(max_digits=10 , decimal_places=2 , blank=False , null=False , \
                                             default=0 , verbose_name='Current fill level (Kg)' , validators=[MinValueValidator(0)]) 
    critical_threshold = models.DecimalField(max_digits=10 , decimal_places=2 , blank=False , null=False , \
                                             default=80 , verbose_name='Critical threshold (%)') 
    status = models.CharField(max_length=20 , blank=False , null=False , choices=status_choices , default='Available')
    last_collected_at = models.DateTimeField(blank=False , null=False , default=timezone.now()) # non input field


    def __str__(self):
        return self.bin_type + ' bin / ' + self.location









class Truck(models.Model):
    truck_status = [
                    ('Available' , 'Available') ,
                    ('Almost full' , 'Almost full'),
                    ('Full' , 'Full')
                   ]
    
    truck_speed = [
                    ('Slow' , 'Slow') ,
                    ('Normal' , 'Normal') ,
                    ('Fast' , 'Fast')
                 ]
    
    organization = models.ForeignKey(Organization , related_name='trucks' , blank=False , null=False , on_delete=models.CASCADE)
    license_plate = models.CharField(max_length=8 , blank=False , null=False , unique=True)
    location = models.CharField(max_length=100 , blank=False , null=False)
    capacity = models.IntegerField(blank=False , null=False , validators=[MinValueValidator(300) , MaxValueValidator(1000)] , verbose_name='Capacity (Kg)')
    current_load = models.DecimalField(max_digits=10 , decimal_places=2 , blank=False , null=False , default=0) 
    status = models.CharField(max_length=20 , blank=False , null=False , choices=truck_status , default='Available')
    speed_category = models.CharField(max_length=10 , blank=False , null=False , choices=truck_speed , default='Normal')
    # Each truck has a specific constant speed (eg: 60km/h)
    speed = models.IntegerField(blank=False , null=False) 
    unload = models.BooleanField(default=False)



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
            if(not self.unload):
                self.current_load = random.randint(0 , int(self.capacity))
            else:
                self.current_load = 0

            if(self.speed_category == 'Slow'):
                self.speed = 40
            elif(self.speed_category == 'Normal'):
                self.speed = 55
            elif(self.speed_category == 'Fast'):
                self.speed = 70
        
        return super().save(*args , **kwargs)



    def __str__(self):
        return self.license_plate + ' / ' + self.location






class PickUpRequest(models.Model):
    status_choices = [
                        ('Pending' , 'Pending') ,
                        ('Scheduled' , 'Scheduled') ,
                        ('Completed' , 'Completed')
                     ]
    
    urgency_level_choices = [
                                ('Normal' , 'Normal') ,
                                ('High' , 'High') ,
                                ('Critical' , 'Critical') ,
                                ('Hazardous' , 'Hazardous')
                            ]
    
    time_interval = [
                        ('Daily' , 'Daily') ,
                        ('Weekly' , 'Weekly') ,
                        ('Monthly' , 'Monthly')
                    ]
    
    bin = models.ForeignKey(Bin , on_delete=models.SET_NULL , blank=True , null=True , related_name='pickup_requests')
    expected_weight = models.IntegerField(blank=False , null=False , default=100)
    truck = models.ForeignKey(Truck , on_delete=models.SET_NULL , blank=True , null=True , related_name='pickup_requests')
    auto_assign_truck = models.BooleanField(default=True , help_text='Automatically truck selection for optimal pickup.')
    status = models.CharField(max_length=12 , blank=False , null=False , choices=status_choices , default='Pending')
    urgency_level = models.CharField(max_length=15 , blank=False , null=False , choices=urgency_level_choices , default='Normal') 
    requested_by = models.ForeignKey(Organization , on_delete=models.CASCADE , related_name='pickup_requests') 
    requested_at = models.DateTimeField(auto_now_add=True) 
    pickup_at = models.DateTimeField(blank=True , null=True) 
    scheduled_at = models.DateTimeField(blank=True , null=True)
    now = models.BooleanField(default=False , help_text='The pick-up will be carried out now.')
    distance = models.DecimalField(max_digits=5 , decimal_places=1 , default=-1)
    expected_time = models.DecimalField(max_digits=5 , decimal_places=1 , default=-1)
    route = models.CharField(max_length=200 , default='NULL -> NULL')
    truck_speed = models.IntegerField(default=0)
    auto_assign_all = models.BooleanField(default=False , help_text='Automatically assign all available trucks to all bins.')
    warnings = models.CharField(max_length=200 , blank=True , null=True)
    processed = models.BooleanField(default=False)


class Collection(models.Model):
    mode = [
                ('Completed' , 'Completed') ,
                ('Partial' , 'Partial') ,
                ('Failed' , 'Failed')
           ]
    pickup_request = models.ForeignKey(PickUpRequest , on_delete=models.CASCADE , related_name='collections')
    collected_weight = models.DecimalField(max_digits=10 , decimal_places=2 , blank=False , null=False)
    collected_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10 , blank=False , null=False , choices=mode , default='Partial')