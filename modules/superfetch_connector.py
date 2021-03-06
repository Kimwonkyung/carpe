# -*- coding: utf-8 -*-
"""module for Superfetch."""
import os, sys
import time
from datetime import datetime, timedelta

from modules import logger
from modules import manager
from modules import interface
from modules.windows_superfetch import sfexport2
from dfvfs.lib import definitions as dfvfs_definitions


class SUPERFETCHConnector(interface.ModuleConnector):

    NAME = 'superfetch_connector'
    DESCRIPTION = 'Module for Superfetch'

    _plugin_classes = {}

    def __init__(self):
        super(SUPERFETCHConnector, self).__init__()

    def Connect(self, configuration, source_path_spec, knowledge_base):

        this_file_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'schema' + os.sep
        # 모든 yaml 파일 리스트
        yaml_list = [this_file_path + 'lv1_os_win_superfetch.yaml']

        # 모든 테이블 리스트
        table_list = ['lv1_os_win_superfetch']

        if not self.check_table_from_yaml(configuration, yaml_list, table_list):
            return False

        if source_path_spec.parent.type_indicator != dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION:
            par_id = configuration.partition_list['p1']
        else:
            par_id = configuration.partition_list[getattr(source_path_spec.parent, 'location', None)[1:]]

        if par_id == None:
            return False

        print('[MODULE]: Superfetch Connect - partition ID(%s)' % par_id)

        # extension -> sig_type 변경해야 함
        query = f"SELECT name, parent_path, extension, ctime, ctime_nano FROM file_info WHERE par_id='{par_id}' and " \
                f"parent_path = 'root/Windows/Prefetch' and (extension = '7db' or extension = 'db' or extension = 'ebd');"

        superfetch_files = configuration.cursor.execute_query_mul(query)

        if len(superfetch_files) == 0:
            return False

        insert_superfetch_info = []

        for superfetch in superfetch_files:
            superfetch_path = superfetch[1][superfetch[1].find('/'):] + '/' + superfetch[0]  # full path
            fileExt = superfetch[2]
            fileName = superfetch[0]

            output_path = configuration.root_tmp_path + os.path.sep + configuration.case_id \
                          + os.path.sep + configuration.evidence_id + os.path.sep + par_id

            if not os.path.exists(output_path):
                os.mkdir(output_path)

            self.ExtractTargetFileToPath(
                source_path_spec=source_path_spec,
                configuration=configuration,
                file_path=superfetch_path,
                output_path=output_path)

            fn = output_path + os.path.sep + fileName
            try:
                results = sfexport2.main(fn)  # filename, app_path
            except Exception:
                continue

            if not results:
                os.remove(output_path + os.sep + fileName)
                continue

            ### superfetch_info ###
            for result in results['reference_point']:
                insert_superfetch_info.append(tuple([par_id, configuration.case_id, configuration.evidence_id, results['file_info']['Name'], results['file_info']['Volume Name'], results['file_info']['Volume ID'], result]))

            os.remove(output_path + os.sep + fileName)

        query = "Insert into lv1_os_win_superfetch values (%s, %s, %s, %s, %s, %s, %s);"
        configuration.cursor.bulk_execute(query, insert_superfetch_info)


manager.ModulesManager.RegisterModule(SUPERFETCHConnector)