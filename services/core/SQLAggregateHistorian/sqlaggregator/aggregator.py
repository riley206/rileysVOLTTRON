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
import sys

from volttron.platform.agent import utils
from volttron.platform.agent.base_aggregate_historian import AggregateHistorian
from volttron.platform.dbutils import sqlutils

_log = logging.getLogger(__name__)
__version__ = '4.0.0'


class SQLAggregateHistorian(AggregateHistorian):
    """
    Agent to aggregate data in historian based on a specific time period.
    This aggregate historian aggregates data collected by SQLHistorian.
    """

    def __init__(self, config_path, **kwargs):
        """
        Validate configuration, create connection to historian, create
        aggregate tables if necessary and set up a periodic call to
        aggregate data
        :param config_path: configuration file path
        :param kwargs:
        """
        self.dbfuncts_class = None
        self.tables_def = None
        self.table_names = None
        super(SQLAggregateHistorian, self).__init__(config_path, **kwargs)

    def configure(self, config_name, action, config):
        if not config or not isinstance(config, dict):
            raise ValueError("Configuration should be a valid json")

        # 1. Check connection to db instantiate db functions class
        connection = config.get('connection', None)
        assert connection is not None
        database_type = connection.get('type', None)
        assert database_type is not None
        params = connection.get('params', None)
        assert params is not None
        tables_def = config.get('tables_def', None)
        self.tables_def, self.table_names = self.parse_table_def(tables_def)

        class_name = sqlutils.get_dbfuncts_class(database_type)
        self.dbfuncts_class = class_name(connection['params'], self.table_names)
        self.dbfuncts_class.setup_aggregate_historian_tables()
        super(SQLAggregateHistorian, self).configure(
            config_name, action, config)

    def get_topic_map(self):
        return self.dbfuncts_class.get_topic_map()

    def get_agg_topic_map(self):
        return self.dbfuncts_class.get_agg_topic_map()

    def get_aggregation_list(self):
        if self.dbfuncts_class:
            return self.dbfuncts_class.get_aggregation_list()
        else:
            raise Exception("Please configure historian with a valid "
                            "configuration")


    def initialize_aggregate_store(self, aggregation_topic_name, agg_type,
                                   agg_time_period, topics_meta):
        _log.debug("aggregation_topic_name " + aggregation_topic_name)
        _log.debug("topics_meta {}".format(topics_meta))
        self.dbfuncts_class.create_aggregate_store(agg_type, agg_time_period)
        agg_id = self.dbfuncts_class.insert_agg_topic(aggregation_topic_name,
                                                      agg_type,
                                                      agg_time_period)
        self.dbfuncts_class.insert_agg_meta(agg_id, topics_meta)
        self.dbfuncts_class.commit()
        return agg_id

    def update_aggregate_metadata(self, agg_id, aggregation_topic_name,
                                  topic_meta):
        _log.debug("aggregation_topic_name " + aggregation_topic_name)
        _log.debug("topic_meta {}".format(topic_meta))

        self.dbfuncts_class.update_agg_topic(agg_id, aggregation_topic_name)
        self.dbfuncts_class.insert_agg_meta(agg_id, topic_meta)
        self.dbfuncts_class.commit()

    def collect_aggregate(self, topic_ids, agg_type, start_time, end_time):
        return self.dbfuncts_class.collect_aggregate(
            topic_ids,
            agg_type,
            start_time,
            end_time)

    def insert_aggregate(self, topic_id, agg_type, period, end_time,
                         value, topic_ids):
        self.dbfuncts_class.insert_aggregate(topic_id,
                                             agg_type,
                                             period,
                                             end_time,
                                             value,
                                             topic_ids)


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(SQLAggregateHistorian, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception' + str(e))


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
