# -*- coding: utf-8 -*-
"""module for DFIR_NTFS_caller."""

import os

from tqdm import tqdm
from modules import manager
from modules import interface
from modules.NTFS import mft_parser, logfile_parser, usnjrnl_parser
from modules.NTFS.dfir_ntfs import USN, LogFile, MFT
from dfvfs.lib import definitions as dfvfs_definitions



class NTFSConnector(interface.ModuleConnector):
    NAME = 'ntfs_connector'
    DESCRIPTION = 'Module for DFIR_NTFS'

    _plugin_classes = {}

    def __init__(self):
        super(NTFSConnector, self).__init__()
        self._mft_path = None
        self._mftmirr_path = None
        self._usnjrnl_path = None
        self._logfile_path = None
        self._deleted_files = []

    def Connect(self, configuration, source_path_spec, knowledge_base):

        this_file_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'schema' + os.sep + 'ntfs' + os.sep

        yaml_list = [this_file_path + 'lv1_fs_ntfs_mft.yaml',
                     this_file_path + 'lv1_fs_ntfs_logfile_restart_area.yaml',
                     this_file_path + 'lv1_fs_ntfs_logfile_log_record.yaml',
                     this_file_path + 'lv1_fs_ntfs_usnjrnl.yaml']

        table_list = ['lv1_fs_ntfs_mft',
                      'lv1_fs_ntfs_logfile_restart_area',
                      'lv1_fs_ntfs_logfile_log_record',
                      'lv1_fs_ntfs_usnjrnl']

        # # Delete table
        # if configuration.standalone_check:
        #     configuration.cursor.delete_table('lv1_fs_ntfs_mft')

        if not self.check_table_from_yaml(configuration, yaml_list, table_list):
            return False

        if source_path_spec.parent.type_indicator != dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION:
            par_id = configuration.partition_list['p1']
        else:
            par_id = configuration.partition_list[getattr(source_path_spec.parent, 'location', None)[1:]]

        if par_id == None:
            return False

        print('[MODULE]: DFIR_NTFS_Connector Call - partition ID(%s)' % par_id)

        # path, name, ads_name
        file_list = [['/', '$MFT', None], ['/', '$MFTMirr', None], ['/$Extend/', '$UsnJrnl', '$J'],
                     ['/', '$LogFile', None]]

        output_path = configuration.root_tmp_path + os.sep + configuration.case_id + os.sep + \
                      configuration.evidence_id + os.sep + par_id

        for file in file_list:
            self.ExtractTargetFileToPath(source_path_spec=source_path_spec,
                                         configuration=configuration,
                                         file_path=file[0] + file[1],
                                         output_path=output_path,
                                         data_stream_name=file[2])

        self._mft_path = output_path + os.sep + '$MFT'
        self._mftmirr_path = output_path + os.sep + '$MFTMirr'
        self._logfile_path = output_path + os.sep + '$LogFile'
        self._usnjrnl_path = output_path + os.sep + '$UsnJrnl_$J'



        if os.path.exists(self._mft_path):
            print("Start parsing $MFT")
            self.process_mft(par_id, configuration, table_list)

        if os.path.exists(self._mft_path) and os.path.exists(self._logfile_path):
            print("Start parsing $Logfile")
            self.process_logfile(par_id, configuration, table_list)

        if os.path.exists(self._mft_path) and os.path.exists(self._usnjrnl_path):
            print("Start parsing $UsnJrnl")
            self.process_usnjrnl(par_id, configuration, table_list)

    def process_mft(self, par_id, configuration, table_list):
        mft_object = open(self._mft_path, 'rb')

        mft_file = MFT.MasterFileTableParser(mft_object)

        info = tuple([par_id, configuration.case_id, configuration.evidence_id])

        query = f"Insert into {table_list[0]} values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, " \
                f"%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"

        mft_list = []
        for idx, file_record in tqdm(enumerate(mft_file.file_records())):
            try:
                file_paths = mft_file.build_full_paths(file_record, True)
            except MFT.MasterFileTableException:
                continue
            # TODO: file_path 중복 수정
            if not file_paths:
                mft_list.extend(mft_parser.mft_parse(info, mft_file, file_record, file_paths))
            else:
                mft_list.extend(mft_parser.mft_parse(info, mft_file, file_record, [file_paths[0]]))

        print(f'mft num: {len(mft_list)}')
        configuration.cursor.bulk_execute(query, mft_list)

    def process_logfile(self, par_id, configuration, table_list):
        logfile_object = open(self._logfile_path, 'rb')
        mft_object = open(self._mft_path, 'rb')

        log_file = LogFile.LogFileParser(logfile_object)
        mft_file = MFT.MasterFileTableParser(mft_object)

        restart_area_list = []
        log_record_list = []
        info = tuple([par_id, configuration.case_id, configuration.evidence_id])

        for idx, log_item in tqdm(enumerate(log_file.parse_ntfs_records())):
            if not type(log_item):
                continue
            elif type(log_item) is LogFile.NTFSRestartArea:
                output_data = logfile_parser.restart_area_parse(log_item)
                restart_area_list.append(info + tuple(output_data))
            elif type(log_item) is LogFile.NTFSLogRecord:
                output_data = logfile_parser.log_record_parse(log_item, mft_file)
                log_record_list.append(info + tuple(output_data))

        restart_area_query = f"Insert into {table_list[1]} values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
        log_record_query = f"Insert into {table_list[2]} values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"

        print(f'restart area num: {len(restart_area_list)}')
        print(f'log record num: {len(log_record_list)}')
        configuration.cursor.bulk_execute(restart_area_query, restart_area_list)
        configuration.cursor.bulk_execute(log_record_query, log_record_list)

        # if len(self._deleted_files) > 0:
        #     # print('Files and directories with these MFT numbers were deleted (in this order):\n')
        #     self._deleted_files = ' '.join(self._deleted_files)
        # # print(self._deleted_files)

    def process_usnjrnl(self, par_id, configuration, table_list):
        usn_object = open(self._usnjrnl_path, 'rb')
        mft_object = open(self._mft_path, 'rb')
        usn_journal = USN.ChangeJournalParser(usn_object)
        mft_file = MFT.MasterFileTableParser(mft_object)

        query = f"Insert into {table_list[3]} values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"

        usnjrnl_list = []
        for idx, usn_record in tqdm(enumerate(usn_journal.usn_records())):
            usn_tuple = usnjrnl_parser.usnjrnl_parse(mft_file, usn_record)
            values = (par_id, configuration.case_id, configuration.evidence_id) + usn_tuple
            usnjrnl_list.append(values)

        print(f'usnjrnl num: {len(usnjrnl_list)}')
        configuration.cursor.bulk_execute(query, usnjrnl_list)


manager.ModulesManager.RegisterModule(NTFSConnector)
