# -*- coding: utf-8 -*-
"""module for ESE database."""
import os
import struct
import pyesedb
from datetime import datetime, timedelta

from modules import logger
from modules import manager
from modules import interface
from modules.windows_search_db import searchdb_parser
from utility import errors
from dfvfs.lib import definitions as dfvfs_definitions


class SearchDBConnector(interface.ModuleConnector):

	NAME = 'searchdb_connector'
	DESCRIPTION = 'Module for searchdb'
	TABLE_NAME = 'lv1_os_win_searchdb'

	_plugin_classes = {}

	def __init__(self):
		super(SearchDBConnector, self).__init__()

	def Connect(self, configuration, source_path_spec, knowledge_base):
		"""Connector to connect to ESE database modules.

		Args:
			configuration: configuration values.
			source_path_spec (dfvfs.PathSpec): path specification of the source file.
			knowledge_base (KnowledgeBase): knowledge base.

		"""

		this_file_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'schema' + os.sep
		# 모든 yaml 파일 리스트
		yaml_list = [this_file_path + 'lv1_os_win_searchdb_gthr.yaml',
					 this_file_path + 'lv1_os_win_searchdb_gthrpth.yaml']

		# 모든 테이블 리스트
		table_list = ['lv1_os_win_searchdb_gthr',
					  'lv1_os_win_searchdb_gthrpth']

		if not self.check_table_from_yaml(configuration, yaml_list, table_list):
			return False

		if source_path_spec.parent.type_indicator != dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION:
			par_id = configuration.partition_list['p1']
		else:
			par_id = configuration.partition_list[getattr(source_path_spec.parent, 'location', None)[1:]]

		if par_id == None:
			return False

		print('[MODULE]: Windows Search Database Analyzer Start! - partition ID(%s)' % par_id)

		# extension -> sig_type 변경해야 함
		query = f"SELECT name, parent_path, extension, ctime, ctime_nano FROM file_info WHERE par_id='{par_id}' and " \
				f"parent_path = 'root/ProgramData/Microsoft/Search/Data/Applications/Windows' and name = 'Windows.edb';"

		searchdb_file = configuration.cursor.execute_query_mul(query)

		if len(searchdb_file) == 0:
			return False

		# Search artifact paths
		path = '/ProgramData/Microsoft/Search/Data/Applications/Windows/Windows.edb'
		file_object = self.LoadTargetFileToMemory(
			source_path_spec=source_path_spec,
			configuration=configuration,
			file_path=path)

		results = searchdb_parser.main(database=file_object)
		file_object.close()
		insert_searchdb_gthr = []
		insert_searchdb_gthrpth = []

		for idx, result in enumerate(results['SystemIndex_Gthr']):
			if idx == 0:
				continue
			timestamp = struct.unpack('>Q',result[3])[0]  # last_modified
			try:
				time = str(datetime.utcfromtimestamp(timestamp/10000000 - 11644473600)).replace(' ', 'T') + 'Z'
			except Exception:
				time = None
			insert_searchdb_gthr.append(tuple([par_id, configuration.case_id, configuration.evidence_id, str(result[0]),
											   str(result[1]), str(result[2]), time, str(result[4]), str(result[5]), str(result[6]),
											   str(result[7]), str(result[8]), str(result[9]), str(None), str(result[11]), str(result[12]),  # user_data blob 임시 처리
											   str(result[13]), str(result[14]), str(result[15]), str(result[16]), str(result[17]), str(result[18]),
											   str(result[19])]))

		for idx, result in enumerate(results['SystemIndex_GthrPth']):
			if idx == 0:
				continue
			insert_searchdb_gthrpth.append(tuple([par_id, configuration.case_id, configuration.evidence_id, str(result[0]),
											   str(result[1]), str(result[2])]))

		query = "Insert into lv1_os_win_searchdb_gthr values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
		configuration.cursor.bulk_execute(query, insert_searchdb_gthr)

		query = "Insert into lv1_os_win_searchdb_gthrpth values (%s, %s, %s, %s, %s, %s);"
		configuration.cursor.bulk_execute(query, insert_searchdb_gthrpth)
		pass

manager.ModulesManager.RegisterModule(SearchDBConnector)