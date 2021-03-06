# -*- coding: utf-8 -*-
import os
from modules import manager
from modules import interface
from modules import logger
from modules.windows_iconcache import IconCacheParser as ic
from dfvfs.lib import definitions as dfvfs_definitions

class IconCacheConnector(interface.ModuleConnector):
    NAME = 'iconcache_connector'
    DESCRIPTION = 'Module for iconcache_connector'

    _plugin_classes = {}

    def __init__(self):
        super(IconCacheConnector, self).__init__()

    def Connect(self, configuration, source_path_spec, knowledge_base):
        print('[MODULE]: IconCacheConnector Connect')

        this_file_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'schema' + os.sep

        # 모든 yaml 파일 리스트
        yaml_list = [this_file_path + 'lv1_os_win_icon_cache.yaml']
        # 모든 테이블 리스트
        table_list = ['lv1_os_win_icon_cache']

        # 모든 테이블 생성
        if not self.check_table_from_yaml(configuration, yaml_list, table_list):
            return False
        
        try:
            if source_path_spec.parent.type_indicator != dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION:
                par_id = configuration.partition_list['p1']
            else:
                par_id = configuration.partition_list[getattr(source_path_spec.parent, 'location', None)[1:]]

            if par_id == None:
                return False

            owner = ''
            query = f"SELECT name, parent_path, extension FROM file_info WHERE par_id='{par_id}' " \
                    f"and extension = 'db' and size > 24 and name regexp 'iconcache_[0-9]' and ("

            for user_accounts in knowledge_base._user_accounts.values():
                for hostname in user_accounts.values():
                    if hostname.identifier.find('S-1-5-21') == -1:
                        continue
                    query += f"parent_path like '%{hostname.username}%' or "
            query = query[:-4] + ");"

            #print(query)

            iconcache_files = configuration.cursor.execute_query_mul(query)
            #print(f'iconcache_files: {len(iconcache_files)}')
            if len(iconcache_files) == 0:
                return False



            insert_iconcache_info = []

            for iconcache in iconcache_files:
                iconcache_path = iconcache[1][iconcache[1].find('/'):] + '/' + iconcache[0]  # document full path
                fileExt = iconcache[2]
                fileName = iconcache[0]
                owner = iconcache[1][iconcache[1].find('/'):].split('/')[2]
                # Windows.old 폴더 체크
                if 'Windows.old' in iconcache_path:
                    fileExt = iconcache[2]
                    fileName = iconcache[0]
                    owner = iconcache[1][iconcache[1].find('/'):].split('/')[3] + "(Windows.old)"

                output_path = configuration.root_tmp_path + os.sep + configuration.case_id + os.sep + configuration.evidence_id + os.sep + par_id
                img_output_path = output_path + os.sep + "iconcache_img" + os.sep + owner + os.sep + fileName[:-3]
                self.ExtractTargetFileToPath(
                    source_path_spec=source_path_spec,
                    configuration=configuration,
                    file_path=iconcache_path,
                    output_path=output_path)

                fn = output_path + os.path.sep + fileName
                app_path = os.path.abspath(os.path.dirname(__file__)) + os.path.sep + "windows_iconcache"

                results = ic.main(fn, app_path, img_output_path)

                if not results:
                    os.remove(output_path + os.sep + fileName)
                    continue

                for i in range(len(results["ThumbsData"])):
                    if i == 0:
                        continue
                    result = results["ThumbsData"][i]

                    filename = result[0]
                    filesize = result[1]
                    imagetype = result[2]
                    data = result[3]
                    sha1 = result[4]
                    tmp = []

                    tmp.append(par_id)
                    tmp.append(configuration.case_id)
                    tmp.append(configuration.evidence_id)
                    tmp.append(owner)
                    tmp.append(filename)
                    tmp.append(filesize)
                    tmp.append(imagetype)
                    tmp.append(data)
                    tmp.append(sha1)

                    insert_iconcache_info.append(tuple(tmp))

                os.remove(output_path + os.sep + fileName)
                # IconCache

            print('[MODULE]: IconCache')
            query = "Insert into lv1_os_win_icon_cache values (%s, %s, %s, %s, %s, %s, %s, %s, %s);"
            configuration.cursor.bulk_execute(query, insert_iconcache_info)
            print('[MODULE]: IconCache Complete')

        except Exception as e:
            print("IconCache Connector Error", e)


manager.ModulesManager.RegisterModule(IconCacheConnector)
