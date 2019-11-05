from functools import partial

from gym.wrappers import TimeLimit

from .env import *
from .wrappers import *
from .util import min_max_norm, np_distance

"""
This file give the ability to create new environments. Given the inherited class, you will have different classes of
input.

host_ids: give the google drive links id given the os.

asset_name: refer to the right binary folder in unity_assets.
 
vector_state_class: refer to the type of vector that we want. (see in avenue_states.py)

"""


class AvenueCar(BaseAvenue):
    # host_ids = {'linux': '1K122iLjvwL62ApWVaa92HfSWFcS-Lns_'}
    host_ids = {'linux': '1eRKQaRxp2dJL9krKviqyecNv5ikFnMrC'}
    asset_name = 'avenue_follow_car'
    vector_state_class = "AvenueState"
    ctrl_type = ControllerType.CAR

class AvenueCarDev(BaseAvenue):
    host_ids = {'linux': '1K122iLjvwL62ApWVaa92HfSWFcS-Lns_'}
    asset_name = 'avenue_follow_car'
    vector_state_class = "AvenueState"
    ctrl_type = ControllerType.CAR

class AvenueCar_v0(BaseAvenue):
    host_ids = {'linux': '1yjaIkK203Qyf9b8dS98iJ-xv7Q48iIGe'}
    asset_name = 'avenue_follow_car'
    vector_state_class = "AvenueCar"
    ctrl_type = ControllerType.CAR

class AvenueDroneDev(BaseAvenue):
    # TODO: Should we keep this in for the release?
    host_ids = {'linux': '1K122iLjvwL62ApWVaa92HfSWFcS-Lns_'}
    asset_name = 'avenue_follow_car'
    vector_state_class = "Drone"
    ctrl_type = ControllerType.DRONE


class LaneFollowing(AvenueCar):
    def __init__(self, config):
        super().__init__(config=dict(config, task=0))  # TODO: What is task 0?

    def compute_reward(self, s, r, d):
        theta = math.radians(s.angle_to_next_waypoint_in_degrees[0])
        velocity_magnitude = s.velocity_magnitude[0]
        top_speed = s.top_speed[0]
        r = (math.cos(theta) * velocity_magnitude) / top_speed
        if s.close_car[0] == 1 or s.close_pedestrian[0] == 1:
            r = 0
        if d:
            r = -5.

        return min_max_norm(r, -5, 1)

    def compute_terminal(self, s, r, d):
        return d


class Car_v0(AvenueCar_v0):

    # reward_close = -2
    # reward_low_speed = -0.01
    reward_close_pedestrian_car = -1
    reward_ground_col = -5
    reward_pedestrian_hit = -10
    reward_car_hit = -10
    reward_obstacle_hit = -10

    _min_speed = 0.01
    _max_count_low_speed = 100
    _max_dist_next_wp = 20
    _max_count_sidewalk = 20

    def __init__(self, config):
        super().__init__(config=dict(config, task=0))
        self._counter_low_speed = 0
        self._counter_sidewalk = 0

    def reset(self, **kwargs):
        self._counter_low_speed = 0
        self._counter_sidewalk = 0
        return super().reset(**kwargs)

    def step(self, action):
        ob, reward, done, info = super().step(action)

        ob["velocity_magnitude"] = ob["velocity_magnitude"] / 50  # TODO: call the result normalized_velocity_magnitude

        if not(ob["close_car"][0] or ob["close_pedestrian"][0]) and ob["velocity_magnitude"][0] < \
                self._min_speed:
            self._counter_low_speed += 1
        else:
            self._counter_low_speed = 0

        if ob["ground_col"]:
            self._counter_sidewalk += 1

        info["reset"] = self.compute_reset(ob, reward, done)

        done = done or info["reset"]

        return ob, reward, done, info

    def compute_reward(self, s, r, d):
        theta = math.radians(s.angle_to_next_waypoint_in_degrees[0])
        velocity_magnitude = s.velocity_magnitude[0] / 50.  # 50 m/s = 180km/h is the max speed

        normalized_forward_velocity = math.cos(theta) * velocity_magnitude  # in [0, 1]

        # velocity squared is proportional to kinetic energy
        # we want to minimize the car's energy if it goes off the road or hits something

        if s.collide_pedestrian[0]:
            r = self.reward_pedestrian_hit * velocity_magnitude**2
        elif s.collide_car[0]:
            r = self.reward_car_hit * velocity_magnitude**2
        elif s.collide_other[0]:
            r = self.reward_obstacle_hit * velocity_magnitude**2
        elif s.ground_col[0]:
            r = self.reward_ground_col * velocity_magnitude**2
        elif s.close_car[0] or s.close_pedestrian[0]:
            # when close then target speed = 2 m/s
            r = self.reward_close_pedestrian_car * (velocity_magnitude - 0.04)**2  # in [-1, 0]
        else:
            # general target speed = 12.5 m/s = 45km/h
            # v = 0     ->  0
            # v = tgt   ->  1
            # v = max   -> -8
            r = 1 - (normalized_forward_velocity * 4 - 1)**2

        return r  # approx. in [-10, 1]

    # def get_min_reward(self):
    #     return min(self.reward_close, self.reward_ground_col, self.reward_low_speed, self.reward_obstacle_hit,
    #                self.reward_pedestrian_hit, self.reward_car_hit)

    def compute_terminal(self, s, r, d):
        return any((
            s.collide_other[0],
            s.collide_car[0],
            s.collide_pedestrian[0],
            s.ground_col[0],
        ))

    def compute_reset(self, s, r, d):
        return any((
            # np_distance(s["closest_waypoint"], s["position"]) > self._max_dist_next_wp,
            # self._counter_low_speed > self._max_count_low_speed,
            # self._counter_sidewalk and (self._counter_sidewalk > self._max_count_sidewalk or s["ground_col"][0] == 0),
        ))


class AutoSpeed(gym.Wrapper):
    def __init__(self, env, speed_target=28):
        super(AutoSpeed, self).__init__(env)
        self.speed_target = speed_target
        self.action_space = gym.spaces.Box(-1, 1, (1,))
        self.last_speed = 0

    def step(self, action):
        calculated_speed = math.fabs((self.speed_target - self.last_speed) * 0.05)
        action = np.array([calculated_speed, action[0]])
        observation, reward, done, info = self.env.step(action)
        self.last_speed = observation["vector"][3]
        return observation, reward, done, info

    def reset(self, **kwargs):
        return self.env.reset(**kwargs)


def RaceSolo(concat_complex=False):

    def generate_env():
        return LaneFollowing(dict(
            lane_number=2,
            task=0,
            time=random.randint(8, 17),
            city_seed=random.randint(0, 10000),
            width=256,
            height=64,
            night_mode=False,
            road_type=6,
            pedestrian_distracted_percent=random.random(),
            pedestrian_density=0,
            weather_condition=1,
            no_decor=0,
            top_speed=26,  # m/s seems to be only half of the actual top speed
            car_number=0,
            layout=1,  # race track
            done_unity=1,
            starting_speed=random.randint(0, 10),
            hd_rendering=0
        ))

    env = RandomizedEnv(generate_env, n=10000)
    env = TimeLimit(env, max_episode_steps=1000)
    if concat_complex:
        env = ConcatComplex(env, {"rgb": ["rgb"], "vector": ["velocity_magnitude"]})
    # env = DictToTupleWrapper(env, "rgb", ["velocity_magnitude", "velocity", "angular_velocity"])
    else:
        env = DictToTupleWrapper(env, "rgb", ["velocity_magnitude"])
    return env


def make_env(generate_env, concat_complex=False, record_video=False):

    if record_video:
        generate_env = partial(generate_env, skip_frame=0, hd_rendering=1, hd_rendering_width=1920,
                               hd_rendering_height=1024)

    else:
        generate_env = partial(generate_env, skip_frame=4, hd_rendering=0)

    env = RandomizedEnv(generate_env, n=10000)
    env = TimeLimit(env, max_episode_steps=1000)

    if record_video:
        env = VideoSaver(env)

    if concat_complex:
        env = ConcatComplex(env, {"rgb": ["rgb"], "vector": ["velocity_magnitude", "steering_angle"]})
    else:
        env = DictToTupleWrapper(env, "rgb", ["velocity_magnitude", "steering_angle"])
    return env


def RaceSolo_v0(**kwargs):

    def generate_env(**kwargs):
        return Car_v0(dict(
            kwargs,
            lane_number=2,
            task=0,
            time=random.randint(8, 17),
            city_seed=random.randint(0, 10000),
            width=256,
            height=64,
            night_mode=False,
            road_type=6,
            pedestrian_distracted_percent=random.random(),
            pedestrian_density=0,
            weather_condition=1,
            no_decor=0,
            top_speed=26,  # m/s approximately 50 km / h
            car_number=0,
            layout=1,  # race track
            done_unity=1,
            starting_speed=random.randint(0, 10),
            hd_rendering=0
        ))

    return make_env(generate_env, **kwargs)


def RaceObstacles_v0(**kwargs):

    def generate_env(**kwargs):
        return Car_v0(dict(
            kwargs,
            lane_number=2,
            task=0,
            time=random.randint(8, 17),
            city_seed=random.randint(0, 10000),
            width=256,
            height=64,
            night_mode=False,
            road_type=6,
            pedestrian_distracted_percent=random.random(),
            pedestrian_density=0,
            weather_condition=1,
            no_decor=0,
            top_speed=26,  # m/s approximately 50 km / h
            car_number=0,
            layout=1,  # race track
            done_unity=1,
            starting_speed=random.randint(0, 10),
            nb_obstacles=200
        ))

    return make_env(generate_env, **kwargs)


def CityPedestrians_v0(**kwargs):

    def generate_env(**kwargs):
        return Car_v0(dict(
            kwargs,
            lane_number=2,
            task=0,
            time=random.randint(8, 17),
            city_seed=random.randint(0, 10000),
            width=256,
            height=64,
            night_mode=False,
            road_type=0,
            pedestrian_distracted_percent=0.2,
            pedestrian_density=5,
            weather_condition=5,
            no_decor=0,
            top_speed=26,  # m/s approximately 50 km / h
            car_number=0,
            layout=0,
            done_unity=1,
            starting_speed=random.randint(0, 10),
            nb_obstacles=0
        ))

    return make_env(generate_env, **kwargs)


def CityPedestrians(**kwargs):

    def generate_env(**kwargs):
        return LaneFollowing(dict(
            kwargs,
            task=0,
            time=12,
            # city_seed=random.randint(0, 10000),
            city_seed=55,
            width=256,
            height=64,
            night_mode=False,
            road_type=0,  # city
            pedestrian_distracted_percent=0.2,
            pedestrian_density=5,
            weather_condition=0,
            no_decor=0,
            top_speed=26,  # m/s approximately 50 km / h
            car_number=20,
            layout=0,  # 0 = straight road, 1 = curvy road, 2 = crossroads
            done_unity=1,
            starting_speed=random.randint(0, 10)  # TODO: what does this do?
        ))

    return make_env(generate_env, **kwargs)
