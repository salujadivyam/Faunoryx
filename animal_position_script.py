#create random path for animals to move
#bearing is the direction as degrees 0/360 90 180 270  
import time as t
import random as rd
import math as mt
def move(lat,lon,stepmax=0.5):
    bearing=rd.uniform(0,360)
    print(bearing)
    dist=rd.uniform(0,stepmax)
    latnew=lat+(dist/111)*mt.cos(mt.radians(bearing))
    lonnew=lon+dist/(111*mt.cos(mt.radians(lat)))*mt.sin(mt.radians(bearing))
    return latnew,lonnew
def haversine(lat,lon,latnew,lonnew,R=6371):
    phi1=mt.radians(lat)
    phi2=mt.radians(latnew)
    lambda1=mt.radians(lon)
    lambda2=mt.radians(lonnew)
    delphi=mt.radians(latnew-lat)
    dellambda=mt.radians(lonnew-lon)
    a=mt.sin(delphi/2)**2 + mt.cos(phi1)*mt.cos(phi2)*mt.sin(dellambda/2)**2
    d=2*R*mt.asin((mt.sin(delphi/2)**2)+mt.cos(phi1)*mt.cos(phi2)*(mt.sin(dellambda/2)**2)**(1/2))
    return d

def movement_speed(lat,latnew,lon,lonnew,time,R=6371):
    dist=haversine(lat,lon,latnew,lonnew,R)
    time=time/3600
    speed=dist/time if time>0 else 0
    return speed

print(move(120,120))
print(haversine(120,120,121,121))
print(movement_speed(120,121,120,121,7200))