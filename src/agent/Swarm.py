import rospy
import time
import threading

from agent.Crazyflie import Crazyflie
from decision_making.DecisionMaking import DecisionMaking
from perception.Perception import Perception
from representations.Constants import RATE
from tools.telemetry.VisualizationPublisher import VisualizationPublisher


class Swarm:
    """
    Defines a swarm of drones. It supports obstacle detection, drone trajectory planning and
    visualization. The number of drones can be changed during runtime. This class is supposed to be
    used with the SwarmController tool, but can also be used independently.
    """

    def __init__(self, drone_ids=None):
        """
        Constructor which initializes drones, decision_making, perception and the visualization
        tool. Note that drones will initialize paused.
        :param drone_ids: List with ids of drones to be used. This list of drones can be changed
        on runtime.
        """

        # drone_ids is mutable
        if drone_ids is None:
            drone_ids = []

        self.__drones = {}
        for i in drone_ids:
            self.__drones[i] = Crazyflie(i)
        self.__decision_making = DecisionMaking(self.__drones)
        self.__perception = Perception()
        self.__visualization_publisher = VisualizationPublisher(self.__drones)
        self.__lock = threading.Lock()
        self.__is_stopped = False

    def run_thread(self):
        """
        Creates a thread and runs the drone's pipeline. It detects obstacles, decides trajectory
        and updates visualizer. The thread will run until stop_thread is called.
        """
        def pipeline():
            while not rospy.is_shutdown() and not self.__is_stopped:
                cur_t = time.time()
                with self.__lock:
                    obstacle_collection = self.__perception.perceive()
                    self.__decision_making.decide(obstacle_collection)
                    self.__visualization_publisher.visualize()
                t_remaining = max(0, 1.0 / RATE - (time.time() - cur_t))
                time.sleep(t_remaining)

        t = threading.Thread(target=pipeline)
        t.start()

    def stop_thread(self):
        """
        Stops the swarm thread from running.
        """
        with self.__lock:
            self.__is_stopped = True

    def unpause(self, goal_pose):
        """
        Unpause all the drones, making them move autonomously again. Note that the drones will
        initialize paused.
        @param goal_pose: Goal pose in the trajectory planner.
        """
        with self.__lock:
            self.__decision_making.unpause(goal_pose)

    def pause(self):
        """
        Pauses all the drones. Their motors will still be running and they will be stabilized in
        their current position. Note that the drones will initialize paused.
        """
        with self.__lock:
            self.__decision_making.pause()

    def shutdown_drone(self, drone_id=0):
        """
        Completely stops a drone, killing its motors.
        :param drone_id: Drone to be stopped.
        """
        with self.__lock:
            if drone_id == 0:
                for key in self.__drones.keys():
                    self.__decision_making.stop_drone(key)
            else:
                self.__decision_making.stop_drone(drone_id)

    def goto_drone(self, drone_id, pose):
        """
        Moves a drone to a given position in a straight line.
        :param drone_id: Drone to be moved.
        :param pose: Desired pose.
        """
        with self.__lock:
            self.__decision_making.goto_drone(drone_id, pose)

    def add_drone(self, drone_id):
        """
        Adds a drone to the dict of used drones.
        :param drone_id: Id of the new drone.
        """
        with self.__lock:
            self.__drones[drone_id] = Crazyflie(drone_id)

    def remove_drone(self, drone_id=0):
        """
        Removes a drone from the dict of used drones.
        :param drone_id: Id of the drone to be removed.
        """
        with self.__lock:
            if drone_id == 0:
                self.__drones.clear()
            else:
                del self.__drones[drone_id]
