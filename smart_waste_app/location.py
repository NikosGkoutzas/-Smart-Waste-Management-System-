from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC




def calculate_distance(start_point , destination):
    options = Options()
    options.binary_location = "/opt/firefox-beta/firefox"
    options.add_argument("--headless") 
    driver = webdriver.Firefox(options=options)
    wait = WebDriverWait(driver , 30)

    driver.get("https://www.google.com/maps")
    click_accept = driver.find_element(By.CSS_SELECTOR , '.VtwTSb > form:nth-child(2) > div:nth-child(1) > div:nth-child(1) > button:nth-child(1) > span:nth-child(6)')
    click_accept.click()
    directions = driver.find_element(By.CSS_SELECTOR , '#hArJGc > span:nth-child(1)')
    directions.click()
    drive_mode = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR , "div.oya4hc:nth-child(2) > button:nth-child(1) > div:nth-child(1)")))
    drive_mode.click()
    inputs = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR , 'input.tactile-searchbox-input')))
    search_start_point = inputs[0]
    search_start_point.click()
    search_start_point.send_keys(start_point)
    search_destination = driver.find_element(By.CSS_SELECTOR , 'input.tactile-searchbox-input')
    search_destination = inputs[1]
    search_destination.click()
    search_destination.send_keys(destination)
    search_button = driver.find_element(By.CSS_SELECTOR , '#directions-searchbox-1 > button:nth-child(2) > span:nth-child(1)')
    search_button.click()
    distance_selection = '#section-directions-trip-0 > div:nth-child(2) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(1)'
    distance = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR , distance_selection)))
    html_distance = distance.get_attribute("innerHTML")
    decimal_digits_distance = int(str(html_distance).split(',')[1].split(' ')[0]) / 10 if(',' in html_distance) else 0
    distance = (int(str(html_distance).split(',')[0]) if(',' in html_distance) else int(str(html_distance).split(' ')[0])) + decimal_digits_distance
    time_selection = '.Fk3sm'
    time_ = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR , time_selection)))
    html_time = time_.get_attribute("innerHTML")
    decimal_digits_time = int(str(html_time).split(',')[1].split(' ')[0]) / 10 if(',' in html_time) else 0
    time_ = ( (float(str(html_time).split(',')[0]) if(',' in html_time) else float(str(html_time).split(' ')[0])) + decimal_digits_time ) * 60
    tMAX = float(3600) # sec (1 hour) / suppose max time between truck and bin
    scaled_time = float((time_ / tMAX ) * 100)
    driver.quit()
    return distance * 1000 if(('χλμ' or 'km') in html_distance) else distance , scaled_time  # in meters , seconds