export { MinioAdminPage } from './pages/MinioAdminPage';
// StorageBrowser 是「存储浏览」页签的实现，独立导出便于在其他宿主复用
// （例如知识库页内嵌某个 bucket 的对象浏览）
export { StorageBrowser } from './components/StorageBrowser';
export { minioAdminApi } from './services/minioAdminApi';
export type {
  MinIOBucket,
  MinIOObject,
  MinIOObjectList,
  MinIOObjectMetadata,
  MinIOStorageStats,
} from './services/minioAdminApi';
