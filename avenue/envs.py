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
 
vector_state_class: refer to the type of vector that we want. (see in rpc.py)

"""


class Car_v0(BaseAvenue):
    host_ids = {'linux': '1yXnjgu1AXg9jUij5VfQ9JQ8ZExpafb86'}
    asset_name = 'avenue_follow_car'
    vector_state_class = "AvenueCar"
    ctrl_type = ControllerType.CAR
    reward_close_pedestrian_car = -1
    reward_ground_col = -5
    reward_pedestrian_hit = -10
    reward_car_hit = -10
    reward_obstacle_hit = -10
    target_velocity = 12.5

    _top_speed = 50

    def __init__(self, config):
        defaults = dict(task=0, skip_frame=4, hd_rendering=0)
        super().__init__(config=dict(defaults, **config))

    def reset(self, **kwargs):
        ob = super().reset(**kwargs)
        ob["velocity_magnitude"] = ob["velocity_magnitude"] / self._top_speed
        return ob

    def step(self, action):
        ob, reward, done, info = super().step(action)
        ob["velocity_magnitude"] = ob["velocity_magnitude"] / self._top_speed

        info["reset"] = self.compute_reset(ob, reward, done)
        done = done or info["reset"]

        return ob, reward, done, info

    def compute_reward(self, s, r, d):
        theta = math.radians(s.angle_to_next_waypoint_in_degrees[0])
        velocity_magnitude = s.velocity_magnitude[0] / self._top_speed  # 50 m/s = 180km/h is the max speed

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
            normalized_target_speed = self.target_velocity / self._top_speed
            r = 1 - (normalized_forward_velocity/normalized_target_speed - 1)**2

        return r  # approx. in [-10, 1]

    def compute_terminal(self, s, r, d):
        return any((
            s.collide_other[0],
            s.collide_car[0],
            s.collide_pedestrian[0],
            s.ground_col[0],
        ))

    def compute_reset(self, s, r, d):
        return s["current_waypoint"][0] > (s["num_waypoints"][0] - 5)


def make_env(conf, concat_complex=False, record_video=False):

    if record_video:
        raise NotImplementedError()
        # generate_env = partial(generate_env, skip_frame=0, hd_rendering=1, hd_rendering_width=1920,
        #                        hd_rendering_height=1024)

    else:
        generate_env = partial(Car_v0, conf)

    env = RandomizedEnv(generate_env, n=10000)
    env = TimeLimit(env, max_episode_steps=1000)

    if record_video:
        env = VideoSaver(env)

    if concat_complex:
        env = ConcatComplex(env, {"rgb": ["rgb"], "vector": ["velocity_magnitude", "steering_angle"]})
    else:
        env = DictToTupleWrapper(env, "rgb", ["velocity_magnitude", "steering_angle"])
    return env


"""
|weather_condition | Control the weather with predefined settings. | [0 - 4] | <ul> <li>0: Clear day</li> <li>1: Light rain</li><li>2:Heavy rain</li> <li>3: Light snow</li> <li>4: Storm </li> </ul> |
|lane_number| Number of lanes. | [1- 12]||
|road_length| Length of the road in meter. | [200-2000]||
|night_mode| Tell if the light are activated or not. | [0-1]| <ul><li>0 : Lights off</li><li> 1: Lights on</li></ul>|
|time| Time of the day (hour only) | [0-23]||
|curvature| Curvature of the road. | [-1000 - 1000]||
|starting_speed| Starting speed of the car. | [0 - 100]||
|vehicle_types| Vehicle type. | [0 - 1]|<ul><li>0: Racing car</li><li>1: SUV</li></ul>|
|City seed| Seed of the city. | [0 - 10000]||
|skip_frame| Number of frame to skip. | [0 - 100]||
|width| Desired width rendering. | [64 - 1024]||
|height| Desired height rendering. | [64 - 1024]||
"""


def RaceSolo_v0(**kwargs):
    defaults = dict(
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
        )
    return make_env(dict(defaults, **kwargs))


def RaceObstacles_v0(**kwargs):
    defaults = dict(
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
    )

    return make_env(dict(defaults, **kwargs))


def CityPedestrians_v0(**kwargs):
    defaults = dict(
        lane_number=2,
        road_length=700,
        task=0,
        time=random.randint(8, 17),
        city_seed=random.randint(0, 10000),
        width=256,
        height=64,
        night_mode=False,
        road_type=0,
        pedestrian_distracted_percent=1,
        pedestrian_density=30,
        weather_condition=5,
        no_decor=0,
        top_speed=26,  # m/s approximately 50 km / h
        car_number=0,
        layout=0,
        done_unity=1,
        starting_speed=random.randint(0, 10),
        nb_obstacles=0
    )

    return make_env(dict(defaults, **kwargs))


def CityCars_v0(**kwargs):
    defaults = dict(
        lane_number=2,
        road_length=700,
        task=0,
        time=random.randint(8, 17),
        city_seed=random.randint(0, 10000),
        width=256,
        height=64,
        night_mode=False,
        road_type=0,  # city
        pedestrian_distracted_percent=1,
        pedestrian_density=30,
        weather_condition=5,
        no_decor=0,
        top_speed=26,  # m/s approximately 50 km / h
        car_number=20,
        layout=0,  # 0 = straight road, 1 = curvy road, 2 = crossroads
        done_unity=1,
        starting_speed=random.randint(0, 10),
        nb_obstacles=0
    )

    return make_env(dict(defaults, **kwargs))
