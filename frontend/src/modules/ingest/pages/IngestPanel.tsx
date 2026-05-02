import { useState, useEffect, useCallback } from 'react';
import { Card, Tabs, Button, Space, Input, Upload, message, Table, Tag, Descriptions, Spin, Alert, Drawer, Empty, Divider, List, Typography, Row, Col, Badge, Steps, Timeline, Popconfirm, Statistic } from 'antd';
import { UploadOutlined, SyncOutlined, CheckCircleOutlined, LoadingOutlined, DatabaseOutlined, ApiOutlined, RobotOutlined, CloudServerOutlined, GitlabOutlined, FolderOutlined, PlusOutlined, EyeOutlined, SwapOutlined, ClockCircleOutlined, CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons';
import { api } from '../../shared';
import { useScenario } from '../../shared';
const { Dragger } = Upload;
const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface ProcessLog {
  id: string;
  timestamp: string;
  stage: 'collection' | 'cleaning' | 'llm' | 'ontology' | 'version' | 'graph';
  operation: string;
  details: Record<string, any>;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string;
  duration_ms?: number;
}

interface IngestRecord {
  id: string;
  source: string;
  source_details?: {
    url?: string;
    query?: string;
    json_length?: number;
    text_length?: number;
    form_data_keys?: string[];
    parties?: string[];
    count?: number;
  };
  status: string;
  record_count: number;
  processed_count: number;
  failed_count: number;
  start_time: string;
  end_time?: string;
  duration_seconds?: number;
  original_content?: string;
  version_id?: string;
  logs?: ProcessLog[];
  builds?: Array<{
    build_id: string;
    status: string;
    document_id: string;
    version_info?: {
      version_id: string;
      commit_message: string;
    };
    entity_count?: number;
    relation_count?: number;
    event_count?: number;
    build_detail?: BuildDetail;
  }>;
}

interface BuildDetail {
  ingest_id: string;
  version_id?: string;
  source: string;
  start_time: string;
  current_stage: number;
  stages: Array<{
    key: string;
    title: string;
    icon: React.ReactNode;
    status: 'wait' | 'process' | 'finish' | 'error';
    logs: ProcessLog[];
  }>;
  entity_count: number;
  relation_count: number;
  event_count: number;
  completed: boolean;
}

const PIPELINE_STAGES = [
  { key: 'collection', title: '数据采集', icon: <DatabaseOutlined /> },
  { key: 'cleaning', title: '数据清洗', icon: <ApiOutlined /> },
  { key: 'llm', title: 'LLM归纳', icon: <RobotOutlined /> },
  { key: 'ontology', title: '本体构建', icon: <CloudServerOutlined /> },
  { key: 'version', title: '版本管理', icon: <GitlabOutlined /> },
  { key: 'graph', title: '图谱生成', icon: <FolderOutlined /> },
];

const STAGE_COLORS: Record<string, string> = {
  collection: 'blue',
  cleaning: 'cyan',
  llm: 'green',
  ontology: 'orange',
  version: 'purple',
  graph: 'red',
};

const PIPELINE_DESCRIPTIONS: Record<string, string> = {
  collection: '从多个数据源收集原始数据',
  cleaning: '清洗和标准化原始数据',
  llm: '使用大语言模型提取结构化信息',
  ontology: '生成OntologyDocument并验证',
  version: '创建版本记录并存储',
  graph: '构建Neo4j图谱',
};

export function IngestPanel() {
  const { currentScenario } = useScenario();
  const [activeTab, setActiveTab] = useState('text');

  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [jsonData, setJsonData] = useState('');
  const [nlDescription, setNlDescription] = useState('');
  const [manualData, setManualData] = useState({
    title: '',
    description: '',
  });

  const [loading, setLoading] = useState(false);
  const [ingestHistory, setIngestHistory] = useState<IngestRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);

  const [buildDetailVisible, setBuildDetailVisible] = useState(false);
  const [currentBuild, setCurrentBuild] = useState<BuildDetail | null>(null);
  const [buildingIngestId, setBuildingIngestId] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const ingests = await api.getIngestHistory(50);
      
      // 获取每个摄入记录的完整状态，包括构建历史
      const ingestsWithBuilds = await Promise.all(
        ingests.map(async (record) => {
          try {
            const fullRecord = await api.getFullIngestRecord(record.id);
            return {
              ...record,
              builds: fullRecord.builds ? [{
                build_id: fullRecord.builds.build_id,
                status: fullRecord.builds.status,
                document_id: fullRecord.builds.document_id,
                version_info: fullRecord.builds.version_id ? {
                  version_id: fullRecord.builds.version_id,
                  commit_message: 'Auto build from pipeline'
                } : undefined,
                entity_count: fullRecord.builds.entity_count,
                relation_count: fullRecord.builds.relation_count,
                event_count: fullRecord.builds.event_count
              }] : undefined,
              version_id: fullRecord.builds?.version_id
            };
          } catch (e) {
            return record;
          }
        })
      );
      
      setIngestHistory(ingestsWithBuilds);
    } catch (error) {
      console.error('加载历史记录失败:', error);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const runBuildPipeline = async (ingestId: string, source: string) => {
    setBuildingIngestId(ingestId);
    const buildStartTime = new Date().toISOString();

    try {
      // 初始构建详情
      const buildDetail: BuildDetail = {
        ingest_id: ingestId,
        source,
        start_time: buildStartTime,
        current_stage: 0,
        stages: PIPELINE_STAGES.map(s => ({
          ...s,
          status: 'wait' as const,
          logs: []
        })),
        entity_count: 0,
        relation_count: 0,
        event_count: 0,
        completed: false
      };

      setCurrentBuild(buildDetail);
      setBuildDetailVisible(true);

      // 调用真实的 API 启动构建
      await api.buildOntology(ingestId);

      // 轮询更新构建进度
      const maxPolls = 60; // 最多轮询 60 次
      let pollCount = 0;
      let isBuildComplete = false;
      
      while (pollCount < maxPolls && !isBuildComplete) {
        await new Promise(resolve => setTimeout(resolve, 500)); // 每 0.5 秒查询一次
        
        const fullRecord = await api.getFullIngestRecord(ingestId);
        
        // 只获取本次构建之后的日志（排除历史构建的旧日志）
        const recentLogs = fullRecord.logs.filter(log => log.timestamp >= buildStartTime);
        
        // 重建构建详情，使用真实的数据
        let completedStagesCount = 0;
        const stages = PIPELINE_STAGES.map((s, index) => {
          const stageLogs = recentLogs.filter(log => log.stage === s.key);
          let stageStatus: 'wait' | 'process' | 'finish' = 'wait';
          
          if (stageLogs.length > 0) {
            const hasCompleted = stageLogs.some(l => l.status === 'completed');
            const hasFailed = stageLogs.some(l => l.status === 'failed');
            const hasProcessing = stageLogs.some(l => l.status === 'processing');
            
            if (hasFailed) {
              stageStatus = 'finish';
              completedStagesCount++;
            } else if (hasCompleted) {
              stageStatus = 'finish';
              completedStagesCount++;
            } else if (hasProcessing) {
              stageStatus = 'process';
            }
          }
          
          return {
            ...s,
            status: stageStatus,
            logs: stageLogs.map(log => ({
              id: log.id,
              timestamp: log.timestamp,
              stage: log.stage as ProcessLog['stage'],
              operation: log.operation,
              details: log.details || {},
              status: log.status as ProcessLog['status'],
              duration_ms: log.duration_ms,
            })),
          };
        });

        buildDetail.stages = stages;
        buildDetail.current_stage = completedStagesCount;
        
        // 检查是否所有阶段都完成或失败了
        const allStagesDone = stages.every(s => s.status === 'finish');
        if (allStagesDone) {
          isBuildComplete = true;
          buildDetail.completed = true;
        }

        setCurrentBuild({ ...buildDetail });
        pollCount++;
      }

      // 构建完成后，获取最终结果
      const fullRecordFinal = await api.getFullIngestRecord(ingestId);
      buildDetail.version_id = fullRecordFinal.builds?.version_id;
      
      // 更新构建历史
      const newBuild = {
        build_id: fullRecordFinal.builds?.build_id || `build-${Date.now()}`,
        status: fullRecordFinal.builds?.status || 'completed',
        document_id: fullRecordFinal.builds?.document_id,
        version_info: {
          version_id: fullRecordFinal.builds?.version_id,
          commit_message: 'Auto build from pipeline'
        },
        entity_count: buildDetail.entity_count,
        relation_count: buildDetail.relation_count,
        event_count: buildDetail.event_count,
        // 保存完整构建过程
        build_detail: buildDetail,
      };

      setIngestHistory(prev => prev.map(record =>
        record.id === ingestId
          ? { ...record, builds: [newBuild], version_id: buildDetail.version_id }
          : record
      ));

      message.success('构建完成！');
    } catch (error) {
      console.error('Build pipeline failed:', error);
      message.error('构建失败，请查看控制台日志');
    } finally {
      setBuildingIngestId(null);
    }
  };

  const getStepDetails = (stage: string, index: number): Record<string, any> => {
    const mockTexts: Record<string, { input: string; output: string }> = {
      collection: {
        input: '{"source": "manual", "format": "text/plain"}',
        output: '{"record_count": 1, "original_content": "5月1日，蓝军向红军阵地发起进攻..."}'
      },
      cleaning: {
        input: '{"original_content": "5月1日，蓝军向红军阵地发起进攻..."}',
        output: '{"cleaned_content": "5月1日蓝军向红军阵地发起进攻", "duplicates_removed": 0}'
      },
      llm: {
        input: '{"cleaned_content": "5月1日蓝军向红军阵地发起进攻", "prompt": "ontology_extraction"}',
        output: '{"entities": [{"id": "e1", "name": "蓝军"}, {"id": "e2", "name": "红军"}], "relations": [{"id": "r1", "type": "攻击", "source": "蓝军", "target": "红军"}]}'
      },
      ontology: {
        input: '{"entities": 2, "relations": 1, "events": 1}',
        output: '{"document_id": "doc-xxx", "entity_count": 2, "relation_count": 1}'
      },
      version: {
        input: '{"document_id": "doc-xxx", "scenario_id": "scenario-xxx"}',
        output: '{"version_id": "v1.0.1746054400", "commit_message": "Auto build"}'
      },
      graph: {
        input: '{"document_id": "doc-xxx", "version_id": "v1.0.1746054400"}',
        output: '{"nodes_created": 2, "edges_created": 1, "indexes_created": 3}'
      }
    };

    const textData = mockTexts[stage] || { input: '{}', output: '{}' };

    switch (stage) {
      case 'collection':
        return {
          input: JSON.parse(textData.input),
          output: JSON.parse(textData.output)
        };
      case 'cleaning':
        return {
          input: JSON.parse(textData.input),
          output: JSON.parse(textData.output)
        };
      case 'llm':
        return {
          input: JSON.parse(textData.input),
          output: JSON.parse(textData.output)
        };
      case 'ontology':
        return {
          input: JSON.parse(textData.input),
          output: JSON.parse(textData.output)
        };
      case 'version':
        return {
          input: JSON.parse(textData.input),
          output: JSON.parse(textData.output)
        };
      case 'graph':
        return {
          input: JSON.parse(textData.input),
          output: JSON.parse(textData.output)
        };
      default:
        return {};
    }
  };

  const formatStepDetails = (details: Record<string, any>) => {
    if (!details) return null;
    
    const { input, output } = details;
    
    return (
      <div style={{ fontSize: 11 }}>
        {input && (
          <div style={{ marginBottom: 4 }}>
            <Text strong style={{ color: '#1890ff' }}>输入:</Text>
            <pre style={{ margin: '2px 0 0 8px', fontSize: 10 }}>
              {JSON.stringify(input, null, 2)}
            </pre>
          </div>
        )}
        {output && (
          <div>
            <Text strong style={{ color: '#52c41a' }}>输出:</Text>
            <pre style={{ margin: '2px 0 0 8px', fontSize: 10 }}>
              {JSON.stringify(output, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  };

  const handleIngestText = async () => {
    if (!text) {
      message.warning('请输入文本内容');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'manual',
        data: text,
        scenario_id: currentScenario,
      });
      message.success(`文本摄入成功，摄入ID: ${result.ingest_id}`);
      setText('');
      await loadHistory();
    } catch (error) {
      message.error('文本摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestNews = async () => {
    if (!url) {
      message.warning('请输入新闻URL');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'news',
        data: url,
        scenario_id: currentScenario,
      });
      message.success(`新闻摄入成功，摄入ID: ${result.ingest_id}`);
      setUrl('');
      await loadHistory();
    } catch (error) {
      message.error('新闻摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestJson = async () => {
    if (!jsonData) {
      message.warning('请输入JSON数据');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'json',
        data: jsonData,
        scenario_id: currentScenario,
      });
      message.success(`JSON摄入成功，摄入ID: ${result.ingest_id}`);
      setJsonData('');
      await loadHistory();
    } catch (error) {
      message.error('JSON摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestNaturalLanguage = async () => {
    if (!nlDescription) {
      message.warning('请输入自然语言描述');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'natural_language',
        data: nlDescription,
        scenario_id: currentScenario,
      });
      message.success(`自然语言摄入成功，摄入ID: ${result.ingest_id}`);
      setNlDescription('');
      await loadHistory();
    } catch (error) {
      message.error('自然语言摄入失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestRandom = async () => {
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'random',
        data: { parties: ['蓝方', '红方'] },
        scenario_id: currentScenario,
      });
      message.success(`随机事件生成成功，摄入ID: ${result.ingest_id}`);
      await loadHistory();
    } catch (error) {
      message.error('随机事件生成失败');
    } finally {
      setLoading(false);
    }
  };

  const handleIngestManual = async () => {
    if (!manualData.title || !manualData.description) {
      message.warning('请输入标题和描述');
      return;
    }
    try {
      setLoading(true);
      const result = await api.ingest({
        type: 'manual',
        data: manualData,
        scenario_id: currentScenario,
      });
      message.success(`手动录入成功，摄入ID: ${result.ingest_id}`);
      setManualData({ title: '', description: '' });
      await loadHistory();
    } catch (error) {
      message.error('手动录入失败');
    } finally {
      setLoading(false);
    }
  };

  const uploadProps = {
    name: 'file',
    multiple: false,
    customRequest: async (options: any) => {
      const { file, onSuccess, onError } = options;
      try {
        setUploadLoading(true);
        await api.ingestFile(file, currentScenario);
        onSuccess();
        message.success(`${file.name} 文件上传成功`);
        await loadHistory();
      } catch (error) {
        onError();
        message.error(`${file.name} 文件上传失败`);
      } finally {
        setUploadLoading(false);
      }
    },
  };

  const handleViewBuild = async (record: IngestRecord) => {
    const hasBuild = record.builds && record.builds.length > 0;
    const build = hasBuild ? record.builds![0] : null;

    // 如果保存了完整构建过程，直接显示
    if (hasBuild && build?.build_detail) {
      setCurrentBuild(build.build_detail);
      setBuildDetailVisible(true);
      return;
    }

    // 尝试获取完整记录（包含详细日志）
    try {
      const fullRecord = await api.getFullIngestRecord(record.id);
      if (fullRecord.logs && fullRecord.logs.length > 0) {
        // 找到最新一次构建的时间范围
        // 先找到所有第一个日志（开始数据采集）的时间戳
        const startLogs = fullRecord.logs.filter(log => log.operation.includes('开始'));
        let buildStartTime = '';
        if (startLogs.length > 0) {
          // 找到最新的开始时间
          buildStartTime = startLogs.sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0].timestamp;
        }

        // 只获取这个时间点之后的日志（最新一次构建的日志）
        const recentLogs = buildStartTime
          ? fullRecord.logs.filter(log => log.timestamp >= buildStartTime)
          : fullRecord.logs;

        // 从API日志重建buildDetail
        const stages = PIPELINE_STAGES.map(s => {
          const stageLogs = recentLogs.filter(log => log.stage === s.key);
          let stageStatus: 'wait' | 'process' | 'finish' = 'wait';
          
          if (stageLogs.length > 0) {
            const hasCompleted = stageLogs.some(l => l.status === 'completed');
            const hasFailed = stageLogs.some(l => l.status === 'failed');
            if (hasFailed || hasCompleted) {
              stageStatus = 'finish';
            }
          }
          
          return {
            ...s,
            status: stageStatus,
            logs: stageLogs.map(log => ({
              id: log.id,
              timestamp: log.timestamp,
              stage: log.stage as ProcessLog['stage'],
              operation: log.operation,
              details: log.details || {},
              status: log.status as ProcessLog['status'],
              duration_ms: log.duration_ms,
            })),
          };
        });

        const buildDetail: BuildDetail = {
          ingest_id: record.id,
          version_id: build?.version_info?.version_id || record.version_id || '未构建',
          source: record.source,
          start_time: buildStartTime || fullRecord.start_time || record.start_time,
          current_stage: hasBuild ? 6 : -1,
          stages: stages,
          entity_count: build?.entity_count || record.record_count || 0,
          relation_count: build?.relation_count || 0,
          event_count: build?.event_count || 0,
          completed: hasBuild,
        };

        setCurrentBuild(buildDetail);
        setBuildDetailVisible(true);
        return;
      }
    } catch (e) {
      console.error('获取完整记录失败:', e);
    }

    // 回退到简化版本
    const buildDetail: BuildDetail = {
      ingest_id: record.id,
      version_id: build?.version_info?.version_id || record.version_id || '未构建',
      source: record.source,
      start_time: record.start_time,
      current_stage: hasBuild ? 6 : -1,
      stages: PIPELINE_STAGES.map(s => ({
        ...s,
        status: hasBuild ? 'finish' as const : 'wait' as const,
        logs: hasBuild ? [{
          id: `log-completed-${s.key}`,
          timestamp: record.end_time || record.start_time,
          stage: s.key as ProcessLog['stage'],
          operation: `${s.title}完成`,
          details: getStepDetails(s.key, 0),
          status: 'completed' as const,
          duration_ms: 500,
        }] : []
      })),
      entity_count: build?.entity_count || record.record_count || 0,
      relation_count: build?.relation_count || 0,
      event_count: build?.event_count || 0,
      completed: hasBuild
    };

    setCurrentBuild(buildDetail);
    setBuildDetailVisible(true);
  };

  const handleBuild = (record: IngestRecord) => {
    runBuildPipeline(record.id, record.source);
  };

  const handleSwitchVersion = (versionId: string) => {
    message.success(`已切换到版本 ${versionId}`);
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      completed: { color: 'success', text: '已完成' },
      processing: { color: 'processing', text: '处理中' },
      pending: { color: 'default', text: '等待中' },
      failed: { color: 'error', text: '失败' },
    };
    const map = statusMap[status] || { color: 'default', text: status };
    return <Tag color={map.color}>{map.text}</Tag>;
  };

  const ingestColumns = [
    {
      title: '时间',
      dataIndex: 'start_time',
      key: 'start_time',
      width: 180,
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (source: string) => {
        const sourceMap: Record<string, string> = {
          news: '新闻',
          manual: '手动',
          json: 'JSON',
          natural_language: '自然语言',
          random: '随机',
          qa_query: '问答',
        };
        return <Tag color="blue">{sourceMap[source] || source}</Tag>;
      },
    },
    {
      title: '原始信息',
      key: 'original_info',
      render: (_: unknown, record: IngestRecord) => {
        const content = record.original_content || record.source_details?.url || record.source_details?.query || '-';
        const display = typeof content === 'string' && content.length > 50
          ? content.substring(0, 50) + '...'
          : content;
        return <span title={String(content)}>{display}</span>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '版本',
      key: 'version',
      width: 120,
      render: (_: unknown, record: IngestRecord) => {
        if (record.builds && record.builds.length > 0) {
          const build = record.builds[0];
          if (build.version_info?.version_id) {
            return (
              <Tag icon={<SwapOutlined />} color="green" style={{ cursor: 'pointer' }} onClick={() => handleSwitchVersion(build.version_info!.version_id)}>
                {build.version_info.version_id}
              </Tag>
            );
          } else if (build.build_id) {
            return <Tag>{build.build_id.substring(0, 8)}...</Tag>;
          } else if (record.version_id) {
            return (
              <Tag icon={<SwapOutlined />} color="green" style={{ cursor: 'pointer' }} onClick={() => handleSwitchVersion(record.version_id!)}>
                {record.version_id}
              </Tag>
            );
          }
        } else if (record.version_id) {
          return (
            <Tag icon={<SwapOutlined />} color="green" style={{ cursor: 'pointer' }} onClick={() => handleSwitchVersion(record.version_id!)}>
              {record.version_id}
            </Tag>
          );
        }
        return <Text type="secondary">-</Text>;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: IngestRecord) => {
        const hasBuild = record.builds && record.builds.length > 0;
        return (
          <Space>
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleViewBuild(record)}
            >
              {hasBuild ? '查看构建' : '详情'}
            </Button>
            {!hasBuild && (
              <Button
                type="primary"
                size="small"
                icon={<PlusOutlined />}
                loading={buildingIngestId === record.id}
                onClick={() => handleBuild(record)}
              >
                构建
              </Button>
            )}
          </Space>
        );
      },
    },
  ];

  const tabItems = [
    {
      key: 'text',
      label: '文本摄入',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <TextArea
            rows={6}
            placeholder="请输入要摄入的文本内容，支持多行输入"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Space style={{ marginTop: 16 }}>
            <Button type="primary" onClick={handleIngestText} loading={loading}>
              开始摄入
            </Button>
            <Button onClick={() => setText('')}>
              清空
            </Button>
          </Space>
        </Card>
      ),
    },
    {
      key: 'news',
      label: '新闻摄入',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <Input
            placeholder="请输入新闻URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            style={{ marginBottom: 16 }}
          />
          <Button type="primary" onClick={handleIngestNews} loading={loading}>
            开始摄入
          </Button>
        </Card>
      ),
    },
    {
      key: 'json',
      label: 'JSON数据',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <TextArea
            rows={8}
            placeholder="请输入JSON格式的本体数据"
            value={jsonData}
            onChange={(e) => setJsonData(e.target.value)}
            style={{ fontFamily: 'monospace' }}
          />
          <Space style={{ marginTop: 16 }}>
            <Button type="primary" onClick={handleIngestJson} loading={loading}>
              开始摄入
            </Button>
            <Button onClick={() => setJsonData('')}>
              清空
            </Button>
          </Space>
        </Card>
      ),
    },
    {
      key: 'natural_language',
      label: '自然语言',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <TextArea
            rows={4}
            placeholder="用自然语言描述一个事件或情况，例如：红方第1装甲旅在B区高地与蓝方第2步兵营发生交火"
            value={nlDescription}
            onChange={(e) => setNlDescription(e.target.value)}
          />
          <Space style={{ marginTop: 16 }}>
            <Button type="primary" onClick={handleIngestNaturalLanguage} loading={loading}>
              开始摄入
            </Button>
            <Button onClick={() => setNlDescription('')}>
              清空
            </Button>
          </Space>
        </Card>
      ),
    },
    {
      key: 'random',
      label: '随机事件',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <Paragraph>生成随机的事件数据，用于测试和演示</Paragraph>
          <Button type="primary" onClick={handleIngestRandom} loading={loading}>
            生成随机事件
          </Button>
        </Card>
      ),
    },
    {
      key: 'manual',
      label: '手动录入',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <Space orientation="vertical" style={{ width: '100%' }}>
            <Input
              placeholder="标题"
              value={manualData.title}
              onChange={(e) => setManualData({ ...manualData, title: e.target.value })}
            />
            <TextArea
              rows={4}
              placeholder="详细描述"
              value={manualData.description}
              onChange={(e) => setManualData({ ...manualData, description: e.target.value })}
            />
            <Space>
              <Button type="primary" onClick={handleIngestManual} loading={loading}>
                提交
              </Button>
              <Button onClick={() => setManualData({ title: '', description: '' })}>
                清空
              </Button>
            </Space>
          </Space>
        </Card>
      ),
    },
    {
      key: 'file',
      label: '文件上传',
      children: (
        <Card style={{ marginBottom: 16 }}>
          <Dragger {...uploadProps}>
            <p className="ant-upload-drag-icon">
              <UploadOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">支持 JSON、TXT、CSV 等格式的文件</p>
          </Dragger>
        </Card>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16}>
        <Col span={24}>
          <Card style={{ marginBottom: 12, borderRadius: 8 }} size="small">
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={tabItems}
              tabPlacement="top"
              size="small"
            />
          </Card>

          <Card
            style={{ borderRadius: 8 }}
            size="small"
            extra={
              <Button size="small" icon={<SyncOutlined />} onClick={loadHistory} loading={loadingHistory}>
                刷新
              </Button>
            }
          >
            {loadingHistory ? (
              <div style={{ textAlign: 'center', padding: 40 }}>
                <Spin />
              </div>
            ) : ingestHistory.length === 0 ? (
              <Empty description="暂无摄入记录，请通过上方方式摄入数据" />
            ) : (
              <Table
                dataSource={ingestHistory}
                columns={ingestColumns}
                rowKey="id"
                pagination={{ pageSize: 10 }}
                size="small"
              />
            )}
          </Card>
        </Col>
      </Row>

      <Drawer
        title={
          <Space>
            <CloudServerOutlined />
            <Text strong>本体构建详情</Text>
            {currentBuild?.version_id && (
              <Tag color="green">{currentBuild.version_id}</Tag>
            )}
          </Space>
        }
        placement="right"
        size="large"
        open={buildDetailVisible}
        onClose={() => setBuildDetailVisible(false)}
      >
        {currentBuild && (
          <Space orientation="vertical" size="large">
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="摄入ID">{currentBuild.ingest_id}</Descriptions.Item>
              <Descriptions.Item label="来源">
                <Tag color="blue">{currentBuild.source}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="开始时间">
                {new Date(currentBuild.start_time).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                {currentBuild.completed ? (
                  <Tag color="success" icon={<CheckCircleFilled />}>构建完成</Tag>
                ) : (
                  <Tag color="processing" icon={<LoadingOutlined />}>构建中</Tag>
                )}
              </Descriptions.Item>
            </Descriptions>

            <Card title="构建进度" size="small">
              <Steps
                current={currentBuild.current_stage}
                size="small"
                items={currentBuild.stages.map(stage => ({
                  title: stage.title,
                  status: stage.status,
                  icon: stage.icon,
                }))}
              />
            </Card>

            <Card title="处理日志" size="small">
              <Timeline
                items={currentBuild.stages.flatMap(stage =>
                  stage.logs.map(log => ({
                    color: log.status === 'completed' ? 'green' : log.status === 'failed' ? 'red' : 'blue',
                    content: (
                      <Space orientation="vertical" size={0}>
                        <Space>
                          <Text strong>{log.operation}</Text>
                          <Tag color={STAGE_COLORS[log.stage]}>{log.stage}</Tag>
                          {log.status === 'completed' ? (
                            <CheckCircleFilled style={{ color: '#52c41a' }} />
                          ) : log.status === 'failed' ? (
                            <CloseCircleFilled style={{ color: '#ff4d4f' }} />
                          ) : (
                            <LoadingOutlined spin />
                          )}
                        </Space>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {new Date(log.timestamp).toLocaleTimeString('zh-CN')}
                          {log.duration_ms && ` - ${log.duration_ms.toFixed(0)}ms`}
                        </Text>
                        {log.details && Object.keys(log.details).length > 0 && formatStepDetails(log.details)}
                      </Space>
                    ),
                  }))
                )}
              />
            </Card>

            {currentBuild.completed && (
              <>
              <Card title="构建结果" size="small">
                <Row gutter={16}>
                  <Col span={8}>
                    <Card size="small">
                      <Statistic
                        title="实体数量"
                        value={currentBuild.entity_count}
                        styles={{ content: { color: '#1890ff' } }}
                      />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small">
                      <Statistic
                        title="关系数量"
                        value={currentBuild.relation_count}
                        styles={{ content: { color: '#52c41a' } }}
                      />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small">
                      <Statistic
                        title="事件数量"
                        value={currentBuild.event_count}
                        styles={{ content: { color: '#722ed1' } }}
                      />
                    </Card>
                  </Col>
                </Row>
              </Card>

              <Card title="本体架构说明" size="small">
                <Descriptions bordered column={1} size="small">
                  <Descriptions.Item label="文档格式">OntologyDocument</Descriptions.Item>
                  <Descriptions.Item label="实体类型">
                    <Space wrap>
                      <Tag color="blue">Unit</Tag>
                      <Tag color="green">Equipment</Tag>
                      <Tag color="orange">Location</Tag>
                      <Tag color="purple">Person</Tag>
                    </Space>
                  </Descriptions.Item>
                  <Descriptions.Item label="关系类型">
                    <Space wrap size={[4, 4]}>
                      <Tag>engaged_with</Tag>
                      <Tag>commands</Tag>
                      <Tag>supported_by</Tag>
                      <Tag>deployed_at</Tag>
                    </Space>
                  </Descriptions.Item>
                  <Descriptions.Item label="事件类型">
                    <Space wrap size={[4, 4]}>
                      <Tag color="orange">contact</Tag>
                      <Tag color="red">attack</Tag>
                      <Tag color="blue">retreat</Tag>
                    </Space>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
              </>
            )}
          </Space>
        )}
      </Drawer>
    </div>
  );
}

export default IngestPanel;
