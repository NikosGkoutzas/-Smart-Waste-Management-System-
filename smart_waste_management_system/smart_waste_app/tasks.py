from celery import shared_task
from .location import calculate_distance
from django.utils import timezone
from datetime import timedelta
from .models import *

''' CELERY BEAT COMMAND
celery -A smart_waste_management_system worker -l info -P solo -B
'''




@shared_task
def calculate_distance_task(start_point , destination):
    time_before_calculation = timezone.now() + timedelta(hours=3)
    distanceResult =  calculate_distance(start_point , destination)
    time_after_calculation = timezone.now() + timedelta(hours=3)
    calculation_delay = (time_after_calculation - time_before_calculation).seconds
    
    return distanceResult , calculation_delay





@shared_task
def create_pickup_request(user_id , org_id):
    pickup_requests = PickUpRequest.objects.filter(requested_by=org_id)

    for pickup in pickup_requests:
        if(pickup and pickup.status != 'Completed'):
            distance = 0
            calc_delay = 0

            
            if(pickup.auto_assign_truck):
                trucks = Truck.objects.filter(organization=org_id).all()
                truck_time_array = []
                truck_select = []
                
                distance = 0
                calc_delay = 0
                for truck in trucks:
                    distance , calc_delay = calculate_distance_task.run(truck.location , pickup.bin.location)
                    truck_time_array.append(calc_delay)
                    truck_select.append(truck)

                best_truck = truck_select[truck_time_array.index(min(truck_time_array))]
                for multiple_best_truck in truck_select:
                    if(multiple_best_truck != best_truck and multiple_best_truck.current_load < best_truck.current_load):
                        best_truck = multiple_best_truck

                pickup.truck = best_truck
                pickup.truck.location = best_truck.location
                pickup.truck.license_plate = best_truck.license_plate
                pickup.distance = distance
                pickup.expected_time = min(truck_time_array)
                pickup.route = f'{best_truck.location}  ->  {pickup.bin.location}'


            else:
                if(not pickup.processed):
                    distance , calc_delay = calculate_distance_task(pickup.truck.location , pickup.bin.location)
                    pickup.distance = distance
                    pickup.expected_time = (distance / pickup.truck.speed) * 1000/3600
                    pickup.route = f'{pickup.truck.location}  ->  {pickup.bin.location}'
                    pickup.processed = True
                    pickup.save(update_fields = ['distance' , 'expected_time' , 'route' , 'processed']) 

            if(not pickup.pickup_at):
                if(pickup.truck.location != pickup.bin.location):
                    if(pickup.now):
                        pickup.pickup_at = timezone.now() + timedelta(hours=3 , seconds=float(pickup.expected_time) + float(calc_delay))
                    
                    else:
                        pickup.pickup_at = pickup.scheduled_at + timedelta(seconds=float(pickup.expected_time) + float(calc_delay))
                    pickup.save(update_fields = ['pickup_at']) 


                else:
                    pickup.distance = 0
                    pickup.expected_time = 0
                    if(pickup.now):
                        pickup.pickup_at = timezone.now() + timedelta(hours=3)
                    else:
                        pickup.pickup_at = pickup.scheduled_at
                    pickup.save(update_fields = ['distance' , 'expected_time' , 'pickup_at']) 
            

            
            if(pickup.pickup_at):
                if(timezone.now() + timedelta(hours=3) < pickup.pickup_at):
                    pickup.status = 'Scheduled'

                else:
                    pickup.status = 'Completed'
                    pickup.truck.current_load += pickup.bin.current_fill_level
                    pickup.bin.current_fill_level = 0
                    
                    if(pickup.truck.current_load + pickup.bin.current_fill_level >= pickup.truck.capacity - 100 and \
                       pickup.truck.current_load + pickup.bin.current_fill_level <= pickup.truck.capacity):
                        pickup.truck.status = 'Almost full'
                    
                    elif(pickup.truck.current_load + pickup.bin.current_fill_level == pickup.truck.capacity):
                        pickup.truck.status = 'Full'
                    pickup.warnings = f'Truck {pickup.truck.license_plate} is {str(pickup.truck.status).lower()}. Empty the truck\'s load before next pickup.'
                    

                pickup.truck.save(update_fields=['status' , 'current_load'])
                pickup.save(update_fields=['status' , 'warnings'])
                pickup.bin.save(update_fields=['current_fill_level'])