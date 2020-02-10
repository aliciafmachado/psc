#!/usr/bin/env python

import math
import rospy
import time
from crazyflie_driver.msg import GenericLogData
from geometry_msgs.msg import Pose, Point
from tf.transformations import quaternion_from_euler

from agent.CrazyflieStateMachine import CrazyflieStateMachine
from decision_making.MeshNode import MeshNode
from decision_making.trajectory.Trajectory import Trajectory
from representations.StablePose import StablePose
from representations.Constants import MAX_VEL_X, MAX_VEL_Y, MAX_VEL_Z, MAX_VEL_YAW
from CrazyflieServices import CrazyflieServices


class Crazyflie:
    """
    Represents a Crazyflie drone. It contains parameters such as id and position, and allows
    controlling the drone.
    """

    def __init__(self, drone_id, high_level=True):
        """
        Basic constructor, initializing state machine, pose subscriber and setting local variables.
        :param drone_id: Crazyflie's id, written directly on the robot.
        :param high_level: TODO: what is this?
        """
        self.__id = drone_id
        self.__state_machine = CrazyflieStateMachine()
        self.__services = CrazyflieServices(drone_id, high_level)
        self.__pose = Pose()
        self.__mesh_node = None
        self.__path = []

        prefix = "/cf" + str(drone_id)
        self.__prefix = prefix
        self.__position_subs = rospy.Subscriber(prefix + '/local_position',
                                                GenericLogData,
                                                self.__pose_callback)

    @property
    def id(self):
        """
        Crazyflie's id, written directly on the robot.
        :return: int
        """
        return self.__id

    @property
    def pose(self):
        """
        Current pose: position, orientation.
        :return: Ros Pose type, with orientation in Quaternion format.
        """
        return self.__pose

    @property
    def stable_pose(self):
        """
        Current pose: position, yaw.
        :return: StablePose object
        """
        return StablePose.from_ros(self.__pose)

    @property
    def mesh_node(self):
        """
        Robot's position in the mesh that represents the world.
        :return: TODO
        """
        return self.__mesh_node

    def set_mesh_node(self, mesh_node):
        """
        Sets the robot's mesh_node.
        :param mesh_node:
        """
        self.__mesh_node = mesh_node

    @property
    def path(self):
        """
        Robot's path to follow.
        :return: List of MeshNodes representing the robot's path.
        """
        return self.__path

    def set_path(self, path):
        """
        Sets the path for the robot to follow.
        :param path: List of MeshNodes representing the robot's path.
        """
        self.__path = path

    def pause(self):
        """
        Makes the drone inactive, stopping its current movement.
        """
        if not self.is_inactive():
            self.goto(self.stable_pose, duration=1)  # Tested a bit and it seems to work with 1.
            # Leaving empty the drone falls.

    def follow_path(self, path):
        """
        Follows a given path in a constant speed.
        :param path: Array of MeshNode, describing a path in the discretized space for the robot to
        follow.
        """
        self.__path = path
        trajectory = Trajectory(path)
        self.follow_trajectory(trajectory)

    def follow_trajectory(self, trajectory):
        """
        Follows a given trajectory.
        :param trajectory: Trajectory object to be followed.
        """
        self.__services.upload_trajectory(trajectory)
        self.__services.start_trajectory()

    def is_inactive(self):
        """
        Checks if the robot is not moving right now. If the robot is stopped, sends the command to
        the drone.
        :return: True if the robot is not moving.
        """
        if self.__state_machine.is_inactive():
            if self.__state_machine.just_stopped():
                self.stop()
            return True
        return False

    def sleep_until_inactive(self, freq=30):
        """
        Sleeps until the drone is inactive. This method will take a while to execute.
        :param freq: Frequency of update in the loop.
        """
        while not self.is_inactive():
            time.sleep(1.0/freq)

    def dist(self, arg):
        """
        Returns the distance to a certain object.
        :param arg: Object to calculate distance. Can be Point, Pose, MeshNode or Crazyflie.
        :return: float, distance to the object.
        """
        p = self.pose.position
        if isinstance(arg, Point):
            return math.hypot(math.hypot(p.x - arg.x, p.y - arg.y), p.z - arg.z)
        elif isinstance(arg, MeshNode):
            return math.hypot(math.hypot(p.x - arg.x, p.y - arg.y), p.z - arg.z)
        elif isinstance(arg, Pose):
            return self.dist(arg.position)
        elif isinstance(arg, StablePose):
            return self.dist(arg.position)
        elif isinstance(arg, Crazyflie):
            return self.dist(arg.pose)
        else:
            raise ValueError("Crazyflie can't calculate distances to object of type " +
                             type(arg).__name__)

    def goto(self, *args, **kwargs):
        """
        Moves the Crazyflie in a straight line to another pose.
        :param args: See below
        :param kwargs: See below

        :Arguments:
            * goal_stable_pose: desired StablePose. Can also be passed as (x, y, z, yaw).
            * goal_x: x for the desired StablePose, if the previous argument is not passed.
            * goal_y: y for the desired StablePose.
            * goal_z: z for the desired StablePose.
            * goal_yaw: yaw for the desired StablePose.

        :Keyword Arguments:
            * relative: Bool if the given pose is global or relative to the drone. Default False.
            * duration: How much time the robot should take to do the task. If -1 will be
              calculated using maximum velocity. Default -1.
            * group_mask: TODO: what is this?

        Examples:
            >> cf.goto(0, 0, 1)
            >> cf.goto(0, 0, 1, 0, relative=False, duration=4.0)
            >> cf.goto(StablePose(0, 0, 1), relative=False, duration=4.0)
        """
        if len(args) == 1:
            goal_stable_pose = args[0]
        else:
            yaw = 0
            if len(args) == 4:
                yaw = args[3]
            goal_stable_pose = StablePose(args[0], args[1], args[2], yaw)

        relative = False
        if 'relative' in kwargs:
            relative = kwargs['relative']

        duration = -1
        if 'duration' in kwargs:
            duration = kwargs['duration']

        group_mask = 0
        if 'group_mask' in kwargs:
            group_mask = kwargs['group_mask']

        self.__goto(goal_stable_pose, relative, duration, group_mask)

    def land(self, target_height=0.0, duration=-1, group_mask=0):
        """
        Lands the drone by descending in a straight line. Does not require the call to the stop
        method after.
        :param target_height: Target height for the drone to land.
        :param duration: How much time to do the whole act of descending.
        :param group_mask: TODO: what is this?
        """
        if duration == -1:
            duration = self.stable_pose.z / MAX_VEL_Z
        self.__services.land(target_height, duration, group_mask)
        self.__state_machine.start_movement(duration, True)

    def stop(self, group_mask=0):
        """
        Stops the drone's motors.
        :param group_mask: TODO: what is this?
        """
        self.__state_machine.stop()
        self.__services.stop(group_mask)

    def __goto(self, goal_stable_pose, relative, duration, group_mask):
        """
        Logic for the goto method.
        :param goal_stable_pose: desired StablePose.
        :param relative: Bool if the given pose is global or relative to the drone.
        :param duration: How much time the robot should take to do the task. If -1 will be
              calculated using maximum velocity.
        :param group_mask: TODO: what is this?
        """
        delta = goal_stable_pose - self.stable_pose
        if duration == -1:
            duration = max(abs(delta.x) / MAX_VEL_X, abs(delta.y) / MAX_VEL_Y,
                           abs(delta.z) / MAX_VEL_Z, abs(delta.yaw) / MAX_VEL_YAW)

        if self.__state_machine.is_stopped():
            self.__takeoff(1)  # Tested a bit and 1m seems to work. I tried putting a really small
            # value but sometimes the drone didn't takeoff.
        self.__services.goto(goal_stable_pose.position, goal_stable_pose.yaw, duration, relative,
                             group_mask)
        self.__state_machine.start_movement(duration)

    def __takeoff(self, target_height, duration=-1, group_mask=0):
        """
        Starts the drone and lifts it to a desired height.
        :param target_height: Desired height to fly.
        :param duration: How much time to go up.
        :param group_mask: TODO: what is this?
        """
        if duration == -1:
            duration = target_height / MAX_VEL_Z
        self.__services.takeoff(target_height, duration, group_mask)

    def __pose_callback(self, data):
        """
        Callback for the subscriber of local_position.
        :param data: Data in the rosmsg
        """
        self.__pose.position.x = data.values[0]
        self.__pose.position.y = data.values[1]
        self.__pose.position.z = data.values[2]
        quaternion = quaternion_from_euler(math.radians(data.values[3]),
                                           math.radians(data.values[4]),
                                           math.radians(data.values[5]))
        self.__pose.orientation.x = quaternion[0]
        self.__pose.orientation.y = quaternion[1]
        self.__pose.orientation.z = quaternion[2]
        self.__pose.orientation.w = quaternion[3]
