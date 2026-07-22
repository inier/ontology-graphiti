import os
import json
import re

modules_to_convert = ['menu-config', 'i18n-admin']
locales = ['zh-CN', 'en-US', 'ja-JP']
src_dir = 'apps/web/src/modules'

term_map = {
    "menuAndPermissionConfig": "菜单与权限配置",
    "menuManagement": "菜单管理",
    "rolePermissionAssignment": "角色权限分配",
    "menuTree": "菜单树",
    "createTopLevelMenu": "新建顶级菜单",
    "loadingMenuTree": "加载菜单树…",
    "emptyMenuHint": "暂无菜单项，点击右上角「新建顶级菜单」创建",
    "menuDetails": "菜单详情",
    "menuDetailsOf": "菜单详情：{{name}}",
    "permissionCode": "权限码",
    "linkType": "链接类型",
    "routePath": "路由路径",
    "iframeUrl": "iframe URL",
    "sortOrder": "排序",
    "active": "启用",
    "inactive": "禁用",
    "visible": "可见",
    "hidden": "隐藏",
    "directory": "目录",
    "menu": "菜单",
    "action": "操作",
    "internal": "内部路由",
    "iframe": "外部 iframe",
    "addChild": "添加子项",
    "edit": "编辑",
    "delete": "删除",
    "confirmDelete": "确认删除？子节点也会一并删除",
    "create": "创建",
    "update": "更新",
    "createSuccess": "创建成功",
    "updateSuccess": "更新成功",
    "deleteSuccess": "已删除",
    "saveFailed": "保存失败",
    "deleteFailed": "删除失败",
    "loadFailed": "加载失败",
    "loadMenuTreeFailed": "加载菜单树失败",
    "loadRoleMenuPermissionFailed": "加载角色菜单权限失败",
    "roleMenuPermissionSaved": "角色菜单权限已保存",
    "loadRoleListFailed": "加载角色列表失败",
    "role": "角色",
    "selectRole": "选择角色",
    "roleMenuPermission": "角色菜单权限",
    "save": "保存",
    "saving": "保存中",
    "pleaseSelectRole": "请选择角色",
    "noRoleSelected": "未选择角色",
    "pleaseSelectRoleHint": "从左侧选择角色以查看/编辑菜单权限",
    "search": "搜索",
    "searchMenu": "搜索菜单",
    "searchRole": "搜索角色",
    "collapseAll": "全部折叠",
    "expandAll": "全部展开",
    "parentMenu": "父级菜单",
    "noParent": "无父级",
    "selectMenuItemHint": "选择左侧菜单项查看详情",
    "yes": "是",
    "no": "否",
    "editMenuItem": "编辑菜单项",
    "createMenuItem": "新建菜单项",
    "namePlaceholder": "i18n key，如 menu.ontology.designer",
    "permissionCodePlaceholder": "如 ontology:designer:view",
    "directoryDescription": "目录（可折叠分组）",
    "menuDescription": "菜单（可导航页面）",
    "actionDescription": "操作（按钮/权限点）",
    "routePathPlaceholder": "如：/users 或 /knowledge",
    "iframePathPlaceholder": "如：/minio-console",
    "iframeUrlPlaceholder": "如：http://localhost:9001",
    "sidebarVisible": "侧边栏可见",
    "description": "描述",
    "descriptionPlaceholder": "菜单项说明",
    "rootDirectory": "根目录",
    "title": "i18n 管理",
    "subtitle": "管理多语言翻译、添加新语言、LLM 自动翻译",
    "addLocale": "新增语言",
    "bulkImport": "批量导入",
    "scanMissing": "扫描缺失",
    "autoTranslate": "LLM 自动翻译",
    "localeCount": "语言数量",
    "translationCount": "翻译条目",
    "moduleCount": "模块数量",
    "coverage": "翻译覆盖",
    "translations": "翻译条目",
    "localeManagement": "语言管理",
    "moduleOverview": "模块概览",
    "filterModule": "模块",
    "filterLocale": "语言",
    "allModules": "全部模块",
    "allLocales": "全部语言",
    "filter": "筛选",
    "key": "Key",
    "module": "模块",
    "locale": "语言",
    "value": "翻译内容",
    "updatedAt": "更新时间",
    "editTranslation": "编辑翻译",
    "translationContent": "翻译内容",
    "enterTranslation": "请输入翻译内容",
    "deleted": "已删除",
    "confirmDeleteTranslation": "确认删除此翻译？",
    "localeCode": "语言代码",
    "englishName": "英文名",
    "nativeName": "本地名称",
    "enabled": "已启用",
    "disabled": "已停用",
    "createdAt": "创建时间",
    "confirmDeactivate": "确认停用",
    "deactivateHint": "停用后将从可用语言列表中移除，但保留已有翻译。",
    "deactivate": "停用",
    "addLocaleTitle": "新增语言",
    "addLocaleHint": "选择预置模板或手动输入。新增后可在 LLM 自动翻译中作为源/目标语言。",
    "quickSelect": "快速选择预置语言",
    "orManualInput": "或手动输入",
    "bcp47Code": "语言代码 (BCP 47)",
    "codePlaceholder": "如: zh-CN / en-US / ja-JP",
    "codeFormat": "格式: zh-CN / en-US",
    "englishNamePlaceholder": "如: Chinese (Simplified)",
    "nativeNamePlaceholder": "如: 简体中文",
    "localeAdded": "语言已新增",
    "addFailed": "新增失败",
    "localeDeactivated": "语言已停用",
    "scanMissingTitle": "扫描缺失翻译",
    "selectModule": "选择模块",
    "targetLocale": "目标语言",
    "scan": "扫描",
    "scanComplete": "扫描完成: 共 {{total}} 个 key，缺失 {{missing}} 个",
    "scanFailed": "扫描失败",
    "noMissing": "翻译完整，无缺失",
    "missingKey": "缺失的 Key",
    "scanResult": "扫描结果",
    "autoTranslateTitle": "LLM 自动翻译",
    "autoTranslateHint": "需要配置 OPENAI_API_KEY 环境变量。源语言条目将被翻译为目标语言。",
    "sourceLocale": "源语言",
    "selectSourceLocale": "选择源语言",
    "selectTargetLocale": "选择目标语言",
    "startTranslate": "开始翻译",
    "autoTranslateComplete": "自动翻译完成: {{translated}}/{{total}}",
    "autoTranslateSkipped": "（跳过 {{skipped}}）",
    "translateFailed": "翻译失败",
    "bulkImportTitle": "批量导入翻译",
    "bulkFormatHint": "每行 4 列，Tab 分隔：",
    "bulkFormatExample": "模块 <TAB> Key <TAB> 语言代码 <TAB> 翻译内容",
    "bulkSampleLine": "workspace <TAB> confirmDelete <TAB> en-US <TAB> Are you sure?",
    "data": "数据",
    "pasteData": "模块\tKey\t语言\t翻译",
    "noValidData": "没有解析到有效数据，请检查格式",
    "bulkImportSuccess": "已批量导入 {{count}} 条翻译",
    "importFailed": "导入失败",
    "addLocaleSuccess": "语言 {{code}} 已新增",
    "selectModuleRequired": "请选择模块",
    "selectSourceRequired": "请选择源语言",
    "selectTargetRequired": "请选择目标语言",
    "codeRequired": "请输入语言代码",
    "englishNameRequired": "请输入英文名称",
    "nativeNameRequired": "请输入本地名称",
    "dataRequired": "请粘贴数据",
    "translationRequired": "请输入翻译内容",
    "noModuleData": "暂无模块数据",
    "localeInfo": "新增语言后，使用 LLM 自动翻译功能可将已有翻译批量翻译为新语言。",
    "totalItems": "共 {{count}} 条",
    "export": "导出",
    "cancel": "取消",
    "edit": "编辑",
    "approved": "已批准",
    "exportTitle": "导出翻译包",
    "selectExportLocale": "选择导出语言",
    "localeRequired": "请选择语言",
    "downloadTemplate": "下载导入模板",
    "templateDownloaded": "模板已下载",
    "uploadFile": "上传文件",
    "uploadHint": "点击或拖拽 .tsv / .txt 文件到此处",
    "uploadHintSub": "支持 Tab 分隔的翻译数据",
    "fileLoaded": "文件已加载到编辑区",
    "orPasteData": "或手动粘贴数据",
}

for module_name in modules_to_convert:
    for locale in locales:
        file_path = os.path.join(src_dir, module_name, 'locales', locale, f'{module_name}.json')
        if not os.path.exists(file_path):
            continue
        
        with open(file_path, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
        
        new_data = {}
        for en_key, value in data.items():
            if en_key in term_map:
                cn_key = term_map[en_key]
                new_data[cn_key] = value
            else:
                new_data[en_key] = value
        
        with open(file_path, 'w', encoding='utf-8') as fp:
            json.dump(new_data, fp, ensure_ascii=False, indent=2)
        
        print(f'Updated: {file_path}')

for module_name in modules_to_convert:
    for root, dirs, files in os.walk(os.path.join(src_dir, module_name)):
        for f in files:
            if f.endswith('.tsx') or f.endswith('.ts'):
                file_path = os.path.join(root, f)
                with open(file_path, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                
                for en_key, cn_key in term_map.items():
                    pattern = r"t\(['\"](" + re.escape(en_key) + r")['\"]\)"
                    replacement = f"t('{cn_key}')"
                    content = re.sub(pattern, replacement, content)
                
                with open(file_path, 'w', encoding='utf-8') as fp:
                    fp.write(content)
                
                print(f'Updated: {file_path}')

print('Done!')
