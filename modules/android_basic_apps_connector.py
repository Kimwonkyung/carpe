# -*- coding: utf-8 -*-
"""module for android basic apps."""

import os

from modules import logger
from modules import manager
from modules import interface
from modules.android_basic_apps import main as android_basic_apps
from utility import errors
from dfvfs.lib import definitions as dfvfs_definitions


class AndroidBasicAppsConnector(interface.ModuleConnector):
    NAME = 'android_basic_apps_connector'
    DESCRIPTION = 'Module for android basic apps'

    def __init__(self):
        super(AndroidBasicAppsConnector, self).__init__()

    def Connect(self, configuration, source_path_spec, knowledge_base):
        """Connector to connect to Android Basic Apps modules.

        Args:
            configuration: configuration values.
            source_path_spec (dfvfs.PathSpec): path specification of the source file.
            knowledge_base (KnowledgeBase): knowledge base.

        """
        if source_path_spec.parent.type_indicator != dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION:
            par_id = configuration.partition_list['p1']
        else:
            par_id = configuration.partition_list[getattr(source_path_spec.parent, 'location', None)[1:]]

        if par_id == None:
            return False

        print('[MODULE]: Android Basic Apps Analyzer Start! - partition ID(%s)' % par_id)

        # Load Schema
        if not self.LoadSchemaFromYaml('../modules/schema/android/lv1_os_and_basic_apps.yaml'):
            logger.error('cannot load schema from yaml: {0:s}'.format(self.NAME))
            return False

        # Search artifact paths
        paths = self._schema['Paths']
        separator = self._schema['Path_Separator']

        find_specs = self.BuildFindSpecs(paths, separator)
        if len(find_specs) < 1:
            return False

        if not configuration.standalone_check:
            output_path = configuration.root_tmp_path
        else:
            output_path = configuration.output_file_path
        output_path += os.sep + configuration.case_id + os.sep + configuration.evidence_id + os.sep + par_id \
                       + os.sep + 'AB2A_Raw_Files'

        if not os.path.exists(output_path):
            os.mkdir(output_path)

        for spec in find_specs:
            self.ExtractTargetDirToPath(source_path_spec=source_path_spec,
                                        configuration=configuration, file_spec=spec,
                                        output_path=output_path)

        results = android_basic_apps.main(output_path)

        header = tuple(['par_id', 'case_id', 'evd_id'])
        header_data = tuple([par_id, configuration.case_id, configuration.evidence_id])
        for result in results:
            if result['number_of_data'] > 0:
                table_name = 'lv1_os_and_basic_app_' + result['title']
                schema = header + result['data_header']

                if not configuration.cursor.check_table_exist(table_name):
                    ret = self.CreateTableWithSchema(configuration.cursor, table_name,
                            schema, configuration.standalone_check)
                    if not ret:
                        logger.error('cannot create database table name: {0:s}'.format(table_name))
                        return False

                header_len = len(header) + result['number_of_data_headers']
                query = f"Insert into {table_name} values ("
                for i in range(0, header_len):
                    if i == header_len - 1:
                        query += "%s);"
                    else:
                        query += "%s, "

                data_list = []
                for data in result['data']:
                    data = header_data + data
                    data_list.append(tuple(data))
                configuration.cursor.bulk_execute(query, data_list)
        print('[MODULE]: Android Basic Apps Analyzer End! - partition ID(%s)' % par_id)


manager.ModulesManager.RegisterModule(AndroidBasicAppsConnector)
