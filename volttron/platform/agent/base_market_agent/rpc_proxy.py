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

import logging
import gevent

from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import PLATFORM_MARKET_SERVICE
from volttron.platform.jsonrpc import RemoteError

_log = logging.getLogger(__name__)
utils.setup_logging()


class RpcProxy:
    """
    The purpose of the RpcProxy is to allow the MarketRegistration to make
    RPC calls on the agent that subclasses of the agent can't see and therefore
    can't make.
    """
    def __init__(self, rpc_call, verbose_logging=True, timeout=60):
        """
        The initalization needs the rpc_call method to grant access to the RPC calls needed to
        communicate with the marketService.
        :param rpc_call: The MarketAgent owns this object.
        """
        self.rpc_call = rpc_call
        self.verbose_logging = verbose_logging
        self.timeout = timeout

    def make_reservation(self, market_name, buyer_seller):
        """
        This call makes a reservation with the MarketService.  This allows the agent to submit a bid and receive
        a cleared market price.

        :param market_name: The name of the market commodity.

        :param buyer_seller: A string indicating whether the agent is buying from or selling to the market.
        The agent shall use the pre-defined strings provided.
        """
        try:
            self.rpc_call(PLATFORM_MARKET_SERVICE, 'make_reservation', market_name, buyer_seller).get(timeout=self.timeout)
            has_reservation = True
        except RemoteError as e:
            has_reservation = False
        except gevent.Timeout as e:
            has_reservation = False
        return has_reservation

    def make_offer(self, market_name, buyer_seller, curve):
        """
        This call makes an offer with the MarketService.

        :param market_name: The name of the market commodity.

        :param buyer_seller: A string indicating whether the agent is buying from or selling to the market.
        The agent shall use the pre-defined strings provided.

        :param curve: The demand curve for buyers or the supply curve for sellers.
        """
        try:
            self.rpc_call(PLATFORM_MARKET_SERVICE, 'make_offer', market_name, buyer_seller,
                          curve.tuppleize()).get(timeout=self.timeout)
            result = (True, None)
            if self.verbose_logging:
                _log.debug("Market: {} {} has made an offer Curve: {}".format(market_name,
                                                                              buyer_seller,
                                                                              curve.points))
        except RemoteError as e:
            result = (False, e.message)
            _log.info(
                "Market: {} {} has had an offer rejected because {}".format(market_name, buyer_seller, e.message))
        except gevent.Timeout as e:
            result = (False, e.message)
            _log.info("Market: {} {} has had an offer rejected because {}".format(market_name, buyer_seller, e.message))
        return result
