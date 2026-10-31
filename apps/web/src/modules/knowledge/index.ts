// F5 归并（AC-22）：Knowledge 两处收敛为一处。
//
// 保留：pages/KnowledgeBase.tsx（1772 行，承载真实功能：知识库 CRUD / 文档上传 /
//      分类树 / 图谱，调用 knowledgeApi，路由 /knowledge 主入口）
// 删除：pages/KnowledgePage.tsx（230 行，仅语义导航 + 同义词 + 扩展规则的次级视图）
// 旧路由 /knowledge/navigation 已在 navigation/legacyRedirects.ts 登记为重定向到 /knowledge。
export { KnowledgeBase } from './pages/KnowledgeBase';
