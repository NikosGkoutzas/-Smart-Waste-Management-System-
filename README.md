# ♻️ Smart Waste Management System  

A complete **Django REST API** for **smart waste management**, supporting organizations, users, bins, trucks, pickup requests, and collection history.  

---

## 🚀 Features

### 👥 Organizations & Users
- Each organization can have **multiple users**.  
- Each user can belong to **one or more organizations**.  
- Users can have **different roles/permissions** per organization (e.g., Admin, Manager, Driver, Viewer).  
- Custom validation for unique emails and usernames.  

### 🗑️ Bins & Trucks
- Bins with defined capacity and current fill level.  
- Trucks with automatic license plate generation.  
- Real-time monitoring of truck load and status: `Empty`, `Almost Full`, `Full`.  

### 🤖 Smart Assignment of Trucks & Collections
- All pickups can be handled **fully automatically**.  
- The system selects the best truck based on:  
  - 🟢 **Shortest distance** to the bin (via Google Maps + Selenium).  
  - 🟢 **Lowest current load** compared to capacity.  
- Bins with **higher fill level** have higher priority.  
- Automatic route generation and ETA calculation.  
- Dynamic truck status updates after each collection.  

### 📦 Pickup Requests
- Support for **immediate** and **scheduled** pickups.  
- Automatic or manual truck assignment.  
- Pickup request statuses: `Pending`, `Scheduled`, `Completed`.  

### 📜 Collections
- Tracking **collection history** per organization.  
- Automatic updates of bins and trucks after each collection.  

### ⏱️ Celery Tasks
- **Celery Beat** for periodic background checks and execution of pickup requests.  
- Distance and ETA calculations via background tasks.  

### 🕒 History Tracking
- Track changes in core models:  
  - Users  
  - Bins  
  - Trucks  
  - Pickup Requests  
  - Collections  

---

## 🛠️ Technologies
- **Backend**: Django, Django REST Framework, DRF Nested Routers  
- **Task Queue**: Celery + Redis  
- **Web Automation**: Selenium (Google Maps distance calculation)  
- **Database**: PostgreSQL / SQLite  
- **History Tracking**: django-simple-history  

---

## 📌 API Structure
