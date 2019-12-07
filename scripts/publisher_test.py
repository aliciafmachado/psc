#!/usr/bin/env python

import rospy
import time
import math

from representations.Constants import RATE
from agent.Crazyflie import Crazyflie
from tools.telemetry.VisualizationPublisher import VisualizationPublisher


# Testing the class VisualizationPublisher.py

def up_and_down(cf):
    rospy.init_node("publisher_test")
    r = rospy.Rate(RATE)
    drones = {1: cf}
    publisher = VisualizationPublisher(drones)
    cf.goto(0, 0, 1.5)
    while not cf.is_inactive():
        publisher.visualize()
        r.sleep()
    cf.land()
    while not cf.is_inactive():
        publisher.visualize()
        r.sleep()

def up_and_down_modified(cf):
    rospy.init_node("publisher_test")
    r = rospy.Rate(RATE)
    drones = {1: cf}
    publisher = VisualizationPublisher(drones)
    cf.goto(0, 0, 1.5)
    while not cf.is_inactive():
        publisher.visualize()
        r.sleep()
    cf.goto(1, 0, 1.5)
    while not cf.is_inactive():
        publisher.visualize()
        r.sleep()
    cf.land()
    while not cf.is_inactive():
        publisher.visualize()
        r.sleep()

if __name__ == '__main__':
    cf = Crazyflie(1)
    up_and_down_modified(cf)
    cf.stop()
