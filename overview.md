# MinIO 存储链路修复

## 问题
知识库上传的 docx 文档未进入 MinIO（WebUI 无 bucket），全部降级到本地磁盘 `data/uploads/kb/`。

## 根因
1. `ensure_bucket()` 返回值未检查，失败后仍调用 `upload_object()`
2. `Minio()` 构造器是惰性的，`available` 属性只检查 `_client is not None`，不反映真实连通性
3. dev 模式 compose override 未显式声明 MINIO 环境变量和 depends_on
4. 容器镜像可能未安装 minio SDK（需重建确认）

## 修复（4 个文件）

| 文件 | 改动 |
|------|------|
| `odap/biz/data/knowledge_base/api/routes.py` | ensure_bucket 返回值检查 + 降级逻辑重构 |
| `odap/infra/storage/minio_client.py` | 修复 delete_object 日志 bug + 新增 ping() 连通性检测 + available 属性增强 |
| `docker/docker-compose.override.yml` | 显式声明 MINIO_* 环境变量 + depends_on 加入 minio |
| `odap/biz/platform/minio_admin/api/routes.py` | /status 端点增强（sdk_installed + detail） |

## 测试
- 24 个单元测试全部通过（含 2 个新增 ping 测试）

## 部署
```bash
python bootstep.py rebuild main   # 重建后端镜像
python bootstep.py dev            # 重启
curl http://localhost:8000/api/minio-admin/status  # 验证连通
```
