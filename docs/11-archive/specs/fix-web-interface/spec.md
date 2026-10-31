---
id: odap.l11.specs-fix-web-interface-spec
status: archived
owner: archivist
version: ''
layer: L11
concern: archive
lifecycle: historical
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: spec-kit 规格件已交付或已废弃，正文由对应 ADR/模块设计承接
governance_evidence: docs/11-archive/README.md 归档说明；spec-kit 流程产物（spec/tasks/checklist 三件套）
---

# 前端界面修复 - Spec

## Why
当前web_interface.py前端界面的角色切换功能和快捷命令功能存在问题，需要修复以符合spec中定义的用户体验需求。

## What Changes
- 修复角色切换按钮的onclick事件处理
- 修复快捷命令区域的动态更新（根据角色显示不同命令）
- 确保Flask后端API正确处理/set_role请求
- 确保window.onload时正确初始化快捷命令

## Impact
- Affected specs: Task 8 (对话界面), Task 11 (可视化界面)
- Affected code: visualization/web_interface.py

## ADDED Requirements
### Requirement: 角色切换功能
角色切换按钮点击后应更新active状态并刷新快捷命令

#### Scenario: 用户点击不同角色
- **WHEN** 用户点击"指挥官"按钮
- **THEN** 按钮active状态更新，后端切换角色，快捷命令更新为指挥官专属命令

### Requirement: 快捷命令动态更新
快捷命令区域应根据当前角色显示不同的命令

#### Scenario: 角色切换后更新快捷命令
- **WHEN** 用户切换角色
- **THEN** 快捷命令区域更新为该角色的专属命令

## MODIFIED Requirements
无

## REMOVED Requirements
无