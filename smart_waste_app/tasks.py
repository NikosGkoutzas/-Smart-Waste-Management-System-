from celery import shared_task
from .location import calculate_distance
from django.utils import timezone
from .models import *
from datetime import timedelta
from .models import *
from django_celery_beat.models import PeriodicTask
import ast , copy


''' CELERY BEAT COMMAND #########################################
celery -A smart_waste_management_system worker -P solo -B -l info
############################################################# '''


@shared_task
def calculate_distance_task(start_point , destination):
    time_before_calculation = local_time()
    distanceResult , scaled_time = calculate_distance(start_point , destination)
    time_after_calculation = local_time()
    calculation_delay = float((time_after_calculation - time_before_calculation).seconds)
    return distanceResult , scaled_time , calculation_delay
 






@shared_task
def create_unload_truck(truck_id , *args , **kwargs):
    
    truck = Truck.objects.filter(id = truck_id).first()
    if(not truck):
        raise ValidationError('Truck not exist.')
    
    
    if(not truck.unloading_time):
        distance , time_ , calc_delay = calculate_distance_task(truck.location , truck.waste_transfer_station)
        
        if(distance != -1):
            total_time = time_ + calc_delay
            truck.unloading_time = local_time() + timedelta(seconds=total_time)
            truck.save()

    else:
        if(local_time() > truck.unloading_time):
            truck.current_load = 0
            truck.save()

            if(not truck.back_to_base_time):
                distance , time_ , calc_delay = calculate_distance_task(truck.waste_transfer_station , truck.base_station)

                if(distance != -1):
                    total_time = time_ + calc_delay
                    truck.back_to_base_time = local_time() + timedelta(seconds=total_time)
                    truck.save()
            else:
                if(local_time() <= truck.back_to_base_time):
                    truck.status = 'Back to base'
                    truck.message = '🚛↩️Truck is returning to base for standby.'
                    truck.save()
                
                else:
                    truck.unloading_time = None
                    truck.back_to_base_time = None
                    PeriodicTask.objects.filter(name__contains = f'unload_truck{truck.id}').last().delete()
                    truck.save()
                    truck.status = 'Available'
                    truck.message = ''
                    truck.save()

       
    








@shared_task
def create_pickup_request(org_id , *args , **kwargs):
    global truck_ranking_per_bin
    global bins_copy
    global max_bins_truck_counter
    global extra_bins_truck_counter
    global max_bins_per_truck
    global extra_bins_for_trucks
    global trucks
    global bins
    global max_bins_truck_counter
    global max_bins_per_truck
    global extra_bins_for_trucks
    global extra_bins_truck_counter
    global distance_b_t
    global travel_time_b_t
    global truck_ranking_per_bin_copied

    pickup_requests = PickUpRequest.objects.filter(organization=org_id).exclude(status__in = ['Completed' , 'Aborted' , 'Cancelled'])    

    bins = list(Bin.objects.filter(organization=org_id , current_fill_level__gt = 0))
    trucks = list(Truck.objects.filter(organization=org_id , status='Available').all())
    

    for pickup in pickup_requests.all():
        distance = 0
        calc_delay = 0
        time_ = 0

        if(pickup.auto_assign_truck):
            if(pickup.bin and pickup.bin.threshold_level < 50):
                pickup.status = 'Aborted'
                pickup.distance = -99
                pickup.warnings = f'Pickup request #{pickup.id} did not scheduled, because {pickup.bin.bin_type} bin at {pickup.bin.location} has not exceeded the threshold level to require emptying.'
                pickup.save()
                return
            
            truck_time_array = []
            truck_select_array = []
            
            for i in range(len(trucks)):
                distance , time_ , calc_delay = calculate_distance_task.run(trucks[i].location , pickup.bin.location)
                truck_time_array.append(calc_delay + time_)
                truck_select_array.append(trucks[i])

            # bubble sort
            for i in range(len(truck_time_array)):
                for j in range(i+1 , len(truck_time_array)):
                    if(truck_time_array[i] > truck_time_array[j]):
                        truck_time_array[i] , truck_time_array[j] = truck_time_array[j] , truck_time_array[i]
                        truck_select_array[i] , truck_select_array[j] = truck_select_array[j] , truck_select_array[i]

            scheduled_pickup_request_list = PickUpRequest.objects.filter(status__in = ['Pending' , 'On the way'] , scheduled_at__isnull=False)
            best_truck = None

            for array_truck in truck_select_array:
                if(array_truck.current_load + pickup.bin.current_fill_level <= array_truck.capacity and array_truck.status == 'Available'):

                    if(pickup.scheduled_at):
                        for sch in scheduled_pickup_request_list:
                            if(sch.bin == bin or sch.truck == truck):   
                                if(pickup.scheduled_at <= sch.scheduled_at + timedelta(minutes=2) and pickup.scheduled_at >= sch.scheduled_at - timedelta(minutes=2)):
                                    continue
                    else:
                        best_truck = array_truck
                        pos = truck_time_array[truck_select_array.index(array_truck)]
                        break
            
            if(best_truck is None):
                pickup.status = 'Aborted'
                pickup.distance = -99
                pickup.warnings = f'Pickup request #{pickup.id} did not scheduled for this {pickup.bin.bin_type} bin at {pickup.bin.location}, as no truck has enough available capacity to accommodate it\'s current weight.'
                pickup.save()

            else:
                pickup.truck = best_truck
                pickup.truck.save()
                pickup.truck.status = 'Unavailable'
                pickup.truck.location = best_truck.location
                pickup.truck.license_plate = best_truck.license_plate
                pickup.truck.save()
                pickup.distance = distance
                pickup.expected_time = pos
                pickup.route = f'{best_truck.location}  ->  {pickup.bin.location}'
                pickup.save()



        elif(pickup.auto_assign_all):       
            task = PeriodicTask.objects.filter(name__contains = 'auto_assign_all').last()
            
            args_list = ast.literal_eval(task.args)
            pickup_requests_ids = args_list[1]
            index = pickup_requests_ids.index(pickup.id)
            
            if(bins and bins[index].threshold_level < 50):
                pickup.status = 'Aborted'
                pickup.distance = -99
                pickup.warnings = f'Pickup request #{pickup.id} did not scheduled, because {bins[index].bin_type} bin at {bins[index].location} has not exceeded the threshold level to require emptying.'
                pickup.save()
                return
            

            if(not PickUpRequest.objects.filter(id__in = pickup_requests_ids , status = 'On the way')):
                bins_copy = bins.copy()
                distance_b_t = [[0 for _ in range(len(bins))] for _ in range(len(trucks))]
                travel_time_b_t = [[0 for _ in range(len(bins))] for _ in range(len(trucks))]
                load_t = [truck.current_load for truck in trucks]
                capacity_t = [truck.capacity for truck in trucks]
                urgency_b = [(bin.current_fill_level / bin.capacity) for bin in bins]
                feasibleTrucks_b = {bin: 0 for bin in bins}
                
                for i in range(len(bins)):
                    for j in range(len(trucks)):
                        if(trucks[j].current_load + bins[i].current_fill_level <= trucks[j].capacity):
                            feasibleTrucks_b[bins[i]] += 1

                
                for j in range(len(trucks)):
                    for i in range(len(bins)):
                        if(trucks[j].location != bins[i].location):
                            distance_b_t[j][i] , travel_time_b_t[j][i] , calc_delay = calculate_distance_task.run(trucks[j].location , bins[i].location)
                            travel_time_b_t[j][i] += calc_delay # add the delay of distance calculation from selenium
                        else:
                            distance_b_t[j][i] = 0
                            travel_time_b_t[j][i] = 0

                dmax = max(max(i) for i in distance_b_t)
                tmax = max(max(i) for i in travel_time_b_t)
                scores = [[0 for _ in range(len(bins))] for _ in range(len(trucks))]

                for j in range(len(trucks)):
                    for i in range(len(bins)):
                        if(dmax == 0 or tmax == 0 or feasibleTrucks_b[bins[i]] == 0):
                            scores[j][i] = 0

                        scores[j][i] = .25 * (distance_b_t[j][i] / dmax) + .25 * (travel_time_b_t[j][i] / tmax) + .25 * (float(load_t[j]) / float(capacity_t[j])) + .25 * (1 - float(urgency_b[i])) + .25 * (1 / float(feasibleTrucks_b[bins[i]]))
                
                '''
                =============================================================================================================================================================
                eg:
                                                                          truck 1                                                         truck 2
                                                       bin 1               bin 2               bin 3                   bin 1               bin 2              bin 3
                scores (2 trucks & 3 bins) -> [ [0.501223649498346, 0.8119343065693432, 0.40549480234560814] , [0.49578598376117444, 0.891818820224719, 0.4070796085185489] ] 
                
                =============================================================================================================================================================
                =============================================================================================================================================================

                EXAMPLE:
                trucks:            Tr 1             Tr 2             Tr 3
                bins:        b1  b2  b3  b4    b1  b2  b3  b4    b1  b2  b3  b4
                scores:    [[5 , 4 , 1 , 6] , [2 , 3 , 4 , 1] , [3 , 6 , 2 , 4]]
                ----------------------------------------------------------------   len(bins) // len(trucks) = 4 // 3 = 1
                Algorithm:
                
                        b1                 b2                   b3                 b4
                [[Tr2 , Tr3 , Tr1] , [Tr2 , Tr1 , Tr3] , [Tr1 , Tr3 , Tr2] , [Tr2 , Tr3 , Tr1]]                   # truck_ranking_per_bin
                
                select  Tr2                 Tr1                 Tr3                 Tr2 (extra)
                =============================================================================================================================================================
                '''
                
                truck_ranking_per_bin = [[] for _ in range(len(bins))]

                for i in range(len(scores[0])):
                    truck_taken_positions_list = []

                    bin_smallest_val = scores[0][i]
                    best_truck = trucks[0]
                    best_pos = 0

                    for j in range(1 , len(scores)):
                        if(scores[j][i] < bin_smallest_val):
                            bin_smallest_val = scores[j][i]
                            best_truck = trucks[j]
                            best_pos = j

                    truck_taken_positions_list.append(best_pos)
                    truck_ranking_per_bin[i].append(best_truck)

                    for _ in range(len(scores) - 1):   
                        next_smallest_val = float('inf')
                        next_best_truck = trucks[0]
                        next_best_pos = 0

                        for l in range(len(scores)):
                            if(l not in truck_taken_positions_list):
                                if(scores[l][i] < next_smallest_val):
                                    next_smallest_val = scores[l][i]
                                    next_best_truck = trucks[l]
                                    next_best_pos = l

                        truck_taken_positions_list.append(next_best_pos)
                        truck_ranking_per_bin[i].append(next_best_truck)
                        

                # urgency levels of every pickup request
                if(bin_smallest_val >= 0 and bin_smallest_val < .25):
                    pickup.urgency_level = 'Hazardous'

                elif(bin_smallest_val >= .25 and bin_smallest_val < .5):
                    pickup.urgency_level = 'Critical'

                elif(bin_smallest_val >= .5 and bin_smallest_val < .75):
                    pickup.urgency_level = 'High'

                elif(bin_smallest_val > .75 and bin_smallest_val <= 1):
                    pickup.urgency_level = 'Normal'
                
                pickup.save()


                truck_ranking_per_bin_copied = copy.deepcopy(truck_ranking_per_bin)
                max_bins_truck_counter = [0 for _ in range(len(trucks))]   # Initialize all trucks with a 0 pickuprequests. Everytime a truck pickup a bin, this number will be increased.
                max_bins_per_truck = len(trucks) // len(bins) if len(trucks) > len(bins) else len(bins) // len(trucks) # max number of assignments of bins for every truck.
                extra_bins_for_trucks = len(trucks) % len(bins) if len(trucks) > len(bins) else len(bins) % len(trucks) # extra bins will be assigned to some trucks, so some trucks will have more assigned bins.
                extra_bins_truck_counter = [0 for _ in range(len(trucks))]

            if(not pickup.pickup_at):
                for truck in truck_ranking_per_bin_copied[0]:
                    activate_extra_truck = True
                    for p in range(len(max_bins_truck_counter)):
                        if(max_bins_truck_counter[p] < max_bins_per_truck):
                            activate_extra_truck = False
                            break

                    if(not activate_extra_truck):
                        if(max_bins_truck_counter[trucks.index(truck)] < max_bins_per_truck):
                            max_bins_truck_counter[trucks.index(truck)] += 1
                            pickup.truck = truck
                            pickup.bin = bins_copy[0]
                            pickup.truck.save()
                            pickup.bin.save()
                            pickup.route = f'{pickup.truck.location}  ->  {pickup.bin.location}'
                            pickup.distance = distance_b_t[trucks.index(pickup.truck)][bins.index(pickup.bin)]
                            pickup.expected_time = travel_time_b_t[trucks.index(pickup.truck)][bins.index(pickup.bin)]
                            pickup.save()
                            break

                    else:
                        if(extra_bins_truck_counter[trucks.index(truck)] < extra_bins_for_trucks):
                            extra_bins_truck_counter[trucks.index(truck)] += 1
                            pickup.truck = truck
                            pickup.bin = bins_copy[0]
                            pickup.truck.save()
                            pickup.bin.save()
                            pickup.route = f'{pickup.truck.location}  ->  {pickup.bin.location}'
                            pickup.distance = distance_b_t[trucks.index(pickup.truck)][bins.index(pickup.bin)]
                            pickup.expected_time = travel_time_b_t[trucks.index(pickup.truck)][bins.index(pickup.bin)]
                            pickup.save()
                            break
                    
                truck_ranking_per_bin_copied.pop(0)
                bins_copy.pop(0)

                truck_ranking_per_bin_copied = copy.deepcopy(truck_ranking_per_bin)

                if(pickup.truck is None):
                    pickup.delete() # This pickup request must delete, because no truck can pickup this specific bin. 
                




        else:
            if(pickup.bin and pickup.bin.threshold_level < 50):
                pickup.status = 'Aborted'
                pickup.distance = -99
                pickup.warnings = f'Pickup request #{pickup.id} did not scheduled, because {pickup.bin.bin_type} bin at {pickup.bin.location} has not exceeded the threshold level to require emptying.'
                pickup.save()
                return
                
            if(not pickup.processed and pickup.truck.location != pickup.bin.location):
                distance , time_ , calc_delay = calculate_distance_task(pickup.truck.location , pickup.bin.location)
                pickup.distance = distance
                pickup.expected_time = calc_delay + time_
                
                pickup.route = f'{pickup.truck.location}  ->  {pickup.bin.location}'
                pickup.processed = True
                pickup.save() 

        if(not pickup.pickup_at):
            if(pickup.truck.location != pickup.bin.location):
                if(pickup.now):
                    pickup.pickup_at = local_time() + timedelta(seconds=float(pickup.expected_time))
                
                else:
                    pickup.pickup_at = pickup.scheduled_at
                pickup.save(update_fields = ['pickup_at']) 


            else:
                pickup.distance = 0
                pickup.expected_time = 0
                if(pickup.now):
                    pickup.pickup_at = local_time()
                    
                else:
                    pickup.pickup_at = pickup.scheduled_at
                pickup.save(update_fields = ['distance' , 'expected_time' , 'pickup_at']) 
        
        if(pickup.pickup_at): 
            if(pickup.now and local_time() < pickup.pickup_at):
                pickup.status = 'On the way'
                pickup.truck.status = 'On route'

            elif(not pickup.now and local_time() >= pickup.pickup_at - timedelta(seconds=float(pickup.expected_time)) and local_time() < pickup.pickup_at):
                pickup.status = 'On the way'
                pickup.truck.status = 'On route'

            elif(local_time() >= pickup.pickup_at):
                pickup.status = 'Completed'
                pickup.truck.status = 'Available'
                prev_truck_current_load = pickup.truck.current_load
                pickup.truck.current_load += pickup.bin.current_fill_level if(pickup.truck.current_load + pickup.bin.current_fill_level <= pickup.truck.capacity) \
                                                                           else pickup.truck.capacity - pickup.truck.current_load

                pickup.picked_weight = pickup.bin.current_fill_level
                pickup.bin.current_fill_level = 0 if(prev_truck_current_load + pickup.bin.current_fill_level <= pickup.truck.capacity) \
                                                  else pickup.bin.current_fill_level - pickup.truck.capacity - prev_truck_current_load
                
                pickup.truck.save()
                pickup.bin.save()
            pickup.save()
        
