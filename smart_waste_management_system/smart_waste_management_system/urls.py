from django.contrib import admin
from django.urls import path , include
from rest_framework_nested import routers
from smart_waste_app.views import *

router = routers.SimpleRouter()
router.register('users' , CustomUserViewSet , basename='users')

user_router = routers.NestedSimpleRouter(router , 'users' , lookup = 'user')
user_router.register('organizations' , OrganizationViewSet , basename = 'user-organizations')

organization_router = routers.NestedSimpleRouter(user_router , 'organizations' , lookup='organization')
organization_router.register('bins' , BinViewSet , basename = 'organization-bins')
organization_router.register('trucks' , TruckViewSet , basename = 'organization-trucks')
organization_router.register('pickuprequests' , PickUpRequestViewSet , basename = 'organization-pickuprequests')
organization_router.register('collections' , CollectionViewSet , basename = 'organization-collections')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('' , include(router.urls)) ,
    path('' , include(user_router.urls)) ,
    path('' , include(organization_router.urls))
]
