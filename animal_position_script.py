#bearing is the direction as degrees 0/360 90 180 270  
import time as t #to calculate total tick times
import random as rd #random position of tigers
import math as mt #used to compute haversine 
import json #need it to use geojson
from turtle import shape #polygons
import uuid
from datetime import datetime, timezone #need these to track and maintain a record
from shapely.geometry import Point #to create a boundary for the nagarahole geojson
from azure.eventhub import EventHubProducerClient
from azure.eventhub import EventData

geojson=r"D:\Faunoryx\Faunoryx\Nagarahole Map.geojson"

#stateless math
class GeoUtils:
    #old and new coordinates after moving
    @staticmethod
    def move(lat,lon,stepmax=0.5):
        bearing=rd.uniform(0,360)
        print(bearing)
        dist=rd.uniform(0,stepmax)
        latnew=lat+(dist/111)*mt.cos(mt.radians(bearing))
        lonnew=lon+dist/(111*mt.cos(mt.radians(lat)))*mt.sin(mt.radians(bearing))
        return latnew,lonnew

    #calculating distance between the 2 points using haversine
    @staticmethod
    def haversine(lat,lon,latnew,lonnew,R=6371):
        phi1=mt.radians(lat)
        phi2=mt.radians(latnew)
        lambda1=mt.radians(lon)
        lambda2=mt.radians(lonnew)
        delphi=mt.radians(latnew-lat)
        dellambda=mt.radians(lonnew-lon)
        a=mt.sin(delphi/2)**2 + mt.cos(phi1)*mt.cos(phi2)*mt.sin(dellambda/2)**2
        d=2*R*mt.asin(mt.sqrt(a))
        return d

    #calculating the movement speed of the tiger
    @staticmethod
    def movement_speed(lat,latnew,lon,lonnew,time,R=6371):
        dist=GeoUtils.haversine(lat,lon,latnew,lonnew,R)
        time=time/3600
        speed=dist/time if time>0 else 0
        return speed

    #creating a border shape from the coordinates in the geojson file
    @staticmethod
    def loadboundary(geojson):
        with open(geojson) as f:
            data=json.load(f)
        boundary=data["features"][0]["geometry"]
        return shape(boundary)

    #checking if the point of the animal exists within the borders or not
    @staticmethod
    def insideboundaryI(lat,lon,boundary):
        return boundary.contains(Point(lon,lat))  #using shapely here, Point(lon,lan) gives a point and contains will check if it is there in boundry or not

#owns one tiger's behaviour and state
class Animal:
    def __init__(self,animalid,startlat,startlon,boundary):
        self.animalid=animalid
        self.lat=startlat
        self.lon=startlon
        self.boundary=boundary
        self.ticks=0
        self.flagged=False

    #checks if the animal has been moving or not in the past 12 hours, if not then flags as anomaly and then this will send a notification via slack and alert the caretakers of the reserve
    def stillness(self,moved,tick_mins=30,flag=12):
        if not moved:
            self.ticks+=1
        else:
            self.ticks=0
            self.Flagged=False
        stillmins=self.ticks*tick_mins
        self.flagged=True if stillmins>flag*60 else False
        return self.flagged


    def excursion(self): #checks if tiger is inside the boundary after every tick
        return not GeoUtils.insideboundary(self.lat,self.lon,self.boundary)


    #if the tiger seems to move faster than its normal speed, there's a chance it could be in a vehicle that belongs to a poacher
    def speed_anomaly(self,newlat,newlon,time,TOP_SPEED=65):
        return GeoUtils.movement_speed(self.lat,newlat,self.lon,newlon,time)>TOP_SPEED


    #one full cycle, one animal one time step, for 1800 seconds and 30 minutes
    def tick(self,stepmax=0.5,tick_mins=30,flag=12,TOP_SPEED=65):
        newlat,newlon=GeoUtils.move(self.lat,self.lon,stepmax=0.5)  #gets new position
        moved=(newlat!=self.lat)or(newlon!=self.lon) #to check if the animal has moved or not
        still=self.stillness(moved,tick_mins,flag)         #checks for animal stillness
        speed=GeoUtils.movement_speed(self.lat,newlat,self.lon,newlon,time=60*tick_mins)    #calculates the speed here, we used 60*tick_mins as 
        fast=self.speed_anomaly(newlat,newlon,time=60*tick_mins,topspeed=65)    #checks if the movement is faster than the topspeed or not

        #now updating the latitute and longitute 
        newlat,newlon=self.lat,self.lon
        outside=self.excursion()   #calling check boundary function
        ping={
            "animal_id":self.animalid,
            "timestamp":datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),  #converted to ist
            "lat":self.lat,                           
            "lon":self.lon,
            "speedkmph":speed,
            "still":still,
            "speed_anomaly":fast,
            "outside_boundary":outside
        }
        return ping                #created a ping dictionary, sends back to caller, readies for event hubs push

    
    @staticmethod
    def ptinboundary(boundary):
        minx,miny,maxx,maxy=boundary.bounds        
        while True:
            lon=rd.uniform(minx,maxx)             #creates random coordinates 
            lat=rd.uniform(miny,maxy)
            if boundary.contains(Point(lon,lat)):   #generates only when the points are within the boundary
                return lat,lon
            

    def spawntigers(boundary,total=149):
        count=0          #initial count starts at 0
        tigers=[]
        tigerid=1       #the tiger id starts from 1
        while count<total:      #ensures count does not exceeds total number of tigers
            rem=total-count
            r=rd.random()
            if r<0.9:        #70% of tigers tend to stay solitary
                size=1
            elif r<0.08:      #20% chance that a tiger may be mating
                size=rd.randint(2,3)
            else:
                size=rd.randint((4,min(rem,6)))   #a very small chance for a tiger to be in an ambush or a group
            size=min(rem,size)

            centre_lat,centre_lon=Animal.ptinboundary(boundary)                 #assigning the random coordinate to a tiger
            for i in range(size):
                jitter_lat=centre_lat+rd.uniform(0.01,-0.01)
                jitter_lon=centre_lon+rd.uniform(0.01,-0.01)                #the coordinates can vary by ±0.01
                if not boundary.contains(Point(jitter_lon,jitter_lat)):     #if the jitter points lie outside the boundary, they are reverted back the the original
                    jitter_lon,jitter_lat=centre_lon,centre_lat
                tigers.append(Animal(f"T{tigerid:03}:",jitter_lat,jitter_lon,boundary))  #adds in the tiger list, the tiger id and the coordinates
                tigerid+=1
                count+=1
        return tigers

#now need a new class for telemetry
class TelemetryPublisher:
    def __init__(self,conn_str,eventhub_name):
        self.conn_str=conn_str
        self.eventhub_name=eventhub_name
        self.producer=EventHubProducerClient.from_connection_string(conn_str=conn_str, eventhub_name=eventhub_name)


    def push(self,ping):
        newping=json.dumps(ping)        #converts the dictionary to JSON
        batch=self.producer.create_batch()  #makes empty batch object
        event_data=EventData(newping)               #makes it as Azure compatible object 
        batch.add(event_data)           #puts wrapped event inside container
        self.producer.send_batch(batch)      #pushes to cloud

    def close(self):
        self.producer.close()


class Simulator:
    def __init__(self,boundary,publisher,tick=1800):     #stores shared stuff like boundary publisher and tick rate
        self.boundary=boundary
        self.publisher=publisher
        self.tick=tick
        self.animals=[]

    def addtiger(self,animal):
        self.animals.append(animal)         #sim needs a list of tigers to manage, this adds them one by one, registers tigers into sim
