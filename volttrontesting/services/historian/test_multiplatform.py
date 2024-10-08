# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}
"""
pytest test cases base historian to test all_platform configuration.
By default all_platform is set to False and historian subscribes only to topics from local message bus.
When all_platforms=True, historian will subscribe to topics from all connected platforms

"""

import os
import random
from datetime import datetime

import gevent
import pytest

from volttron.platform import get_services_core, jsonapi, is_rabbitmq_available
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttrontesting.fixtures.volttron_platform_fixtures import build_wrapper
from volttrontesting.skip_if_handlers import rmq_skipif
from volttrontesting.utils.utils import get_rand_vip, get_hostname_and_random_port
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_vip, \
    get_rand_ip_and_port
from volttron.platform.agent.utils import execute_command
HAS_RMQ = is_rabbitmq_available()
if HAS_RMQ:
    from volttron.utils.rmq_setup import start_rabbit, stop_rabbit


@pytest.fixture(scope="module")
def get_zmq_volttron_instances(request):
    """ Fixture to get more than 1 volttron instance for test
    Use this fixture to get more than 1 volttron instance for test. This
    returns a function object that should be called with number of instances
    as parameter to get a list of volttron instnaces. The fixture also
    takes care of shutting down all the instances at the end

    Example Usage:

    def test_function_that_uses_n_instances(get_volttron_instances):
        instance1, instance2, instance3 = get_volttron_instances(3)

    @param request: pytest request object
    @return: function that can used to get any number of
        volttron instances for testing.
    """
    all_instances = []

    def get_n_volttron_instances(n, should_start=True, address_file=True):
        get_n_volttron_instances.count = n
        vip_addresses = []
        web_addresses = []
        instances = []
        names = []

        for i in range(0, n):
            address = get_rand_vip()
            web_address = "http://{}".format(get_rand_ip_and_port())
            vip_addresses.append(address)
            web_addresses.append(web_address)
            nm = 'platform{}'.format(i + 1)
            names.append(nm)

        for i in range(0, n):
            address = vip_addresses[i]
            web_address = web_addresses[i]
            wrapper = PlatformWrapper(messagebus='zmq', ssl_auth=False)

            addr_file = os.path.join(wrapper.volttron_home, 'external_address.json')
            if address_file:
                with open(addr_file, 'w') as f:
                    jsonapi.dump(web_addresses, f)
                    gevent.sleep(0.5)
            wrapper.startup_platform(address, bind_web_address=web_address, setupmode=True)
            wrapper.skip_cleanup = True
            instances.append(wrapper)

        gevent.sleep(11)
        for i in range(0, n):
            instances[i].shutdown_platform()

        gevent.sleep(1)
        # del instances[:]
        for i in range(0, n):
            address = vip_addresses.pop(0)
            web_address = web_addresses.pop(0)
            print(address, web_address)
            instances[i].startup_platform(address, bind_web_address=web_address)
            instances[i].allow_all_connections()
        gevent.sleep(11)
        instances = instances if n > 1 else instances[0]

        get_n_volttron_instances.instances = instances
        return instances

    return get_n_volttron_instances


@pytest.mark.historian
@pytest.mark.multiplatform
def test_all_platform_subscription_zmq(request, get_zmq_volttron_instances):

    upstream, downstream, downstream2 = get_zmq_volttron_instances(3)

    gevent.sleep(5)

    # setup consumer on downstream1. One with all_platform=True another False

    hist_config = {"connection":
                       {"type": "sqlite",
                        "params": {
                            "database": downstream.volttron_home +
                                        "/historian.sqlite"}},
                   "all_platforms": True
                   }
    hist_id = downstream.install_agent(
        vip_identity='platform.historian',
        agent_dir=get_services_core("SQLHistorian"),
        config_file=hist_config,
        start=True)
    gevent.sleep(3)
    query_agent = downstream.build_agent(identity="query_agent1")
    gevent.sleep(1)

    hist2_config = {"connection":
                        {"type": "sqlite",
                         "params": {
                             "database": downstream2.volttron_home +
                                         "/historian2.sqlite"}},
                    }
    hist2_id = downstream2.install_agent(
        vip_identity='unused.historian',
        agent_dir=get_services_core("SQLHistorian"),
        config_file=hist2_config,
        start=True)
    query_agent2 = downstream2.build_agent(identity="query_agent2")
    gevent.sleep(2)

    print("publish")

    producer = upstream.build_agent(identity="producer")
    gevent.sleep(2)
    DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
    percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading,
                    'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': float_meta,
                    'MixedAirTemperature': float_meta,
                    'DamperSignal': percent_meta
                    }]

    # Create timestamp
    now = utils.format_timestamp(datetime.utcnow())

    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now, headers_mod.TIMESTAMP: now
    }
    print("Published time in header: " + now)

    producer.vip.pubsub.publish('pubsub',
                                DEVICES_ALL_TOPIC,
                                headers=headers,
                                message=all_message).get(timeout=10)

    gevent.sleep(5)

    ## Query from consumer to verify

    result = query_agent.vip.rpc.call("platform.historian",
                                      'query',
                                      topic="Building/LAB/Device/OutsideAirTemperature",
                                      count=1).get(timeout=100)
    print("QUERY RESULT : {}" .format(result))
    assert (result['values'][0][1] == oat_reading)
    assert set(result['metadata'].items()) == set(float_meta.items())
    gevent.sleep(1)

    result = query_agent2.vip.rpc.call("unused.historian",
                                       'query',
                                       topic="Building/LAB/Device/OutsideAirTemperature",
                                       count=1).get(timeout=100)
    print("QUERY RESULT : {}".format(result))
    assert not result

    downstream.remove_agent(hist_id)
    downstream2.remove_agent(hist2_id)
    query_agent.core.stop()
    query_agent2.core.stop()
    producer.core.stop()
    gevent.sleep(1)
    upstream.shutdown_platform()
    downstream.shutdown_platform()
    downstream2.shutdown_platform()


@pytest.mark.historian
@pytest.mark.multiplatform
@pytest.mark.skipif(rmq_skipif, reason="RMQ not installed.")
def test_all_platform_subscription_rmq(request, federated_rmq_instances):
    try:
        upstream, downstream = federated_rmq_instances
        assert upstream.is_running()
        assert downstream.is_running()

        # setup consumer on downstream1. One with all_platform=True another False

        hist_config = {"connection":
                           {"type": "sqlite",
                            "params": {
                                "database": downstream.volttron_home +
                                            "/historian.sqlite"}},
                       "all_platforms": True
                       }
        hist_id = downstream.install_agent(
            vip_identity='platform.historian.rmq',
            agent_dir=get_services_core("SQLHistorian"),
            config_file=hist_config,
            start=True)

        assert downstream.is_running()
        assert downstream.is_agent_running(hist_id)
        query_agent = downstream.dynamic_agent
        gevent.sleep(2)

        print("publish")
        producer = upstream.dynamic_agent
        gevent.sleep(2)
        DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

        oat_reading = random.uniform(30, 100)
        mixed_reading = oat_reading + random.uniform(-5, 5)
        damper_reading = random.uniform(0, 100)

        float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
        percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': oat_reading,
                        'MixedAirTemperature': mixed_reading,
                        'DamperSignal': damper_reading},
                       {'OutsideAirTemperature': float_meta,
                        'MixedAirTemperature': float_meta,
                        'DamperSignal': percent_meta
                        }]

        # Create timestamp
        now = utils.format_timestamp(datetime.utcnow())
        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now, headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)

        producer.vip.pubsub.publish('pubsub',
                                    DEVICES_ALL_TOPIC,
                                    headers=headers,
                                    message=all_message).get(timeout=10)
        gevent.sleep(10)

        ## Query from consumer to verify

        result = query_agent.vip.rpc.call("platform.historian.rmq",
                                          'query',
                                          topic="Building/LAB/Device/OutsideAirTemperature",
                                          count=1).get(timeout=100)
        print("QUERY RESULT : {}".format(result))
        assert (result['values'][0][1] == oat_reading)
        assert set(result['metadata'].items()) == set(float_meta.items())
        gevent.sleep(1)
    finally:
        if downstream:
            downstream.remove_agent(hist_id)
