"""验证引擎实现"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.validation import IValidationEngine
from ..models.validation import ValidationRule, ValidationResult, ValidationIssue, ValidationSeverity
from ..storage.sqlite_ingest_storage import SQLiteIngestStorage


class ValidationEngine(IValidationEngine):

    def __init__(self):
        self.storage = SQLiteIngestStorage()

    def add_validation_rule(self, rule: ValidationRule) -> ValidationRule:
        rule_dict = {
            'rule_id': rule.id,
            'name': rule.name,
            'description': rule.description,
            'rule_type': rule.rule_type,
            'severity': rule.severity.value,
            'condition': {
                'expression': rule.expression,
                'params': rule.params,
            },
            'is_active': rule.enabled,
        }
        self.storage.save_validation_rule(rule_dict)
        return rule

    def get_validation_rule(self, rule_id: str) -> Optional[ValidationRule]:
        row = self.storage.get_validation_rule(rule_id)
        if not row:
            return None
        return self._row_to_rule(row)

    def list_validation_rules(self, filters: Dict[str, Any] = None,
                             page: int = 1, page_size: int = 10) -> List[ValidationRule]:
        rows = self.storage.list_validation_rules(filters, page, page_size)
        return [self._row_to_rule(r) for r in rows]

    def _row_to_rule(self, row: Dict[str, Any]) -> ValidationRule:
        condition = row.get('condition')
        if isinstance(condition, str):
            import json
            try:
                condition = json.loads(condition)
            except Exception:
                condition = {}
        if not isinstance(condition, dict):
            condition = {}
        return ValidationRule(
            id=row.get('rule_id', ''),
            name=row.get('name', ''),
            description=row.get('description', ''),
            rule_type=row.get('rule_type', 'custom'),
            severity=ValidationSeverity(row.get('severity', 'warning')),
            expression=condition.get('expression', '') if condition else '',
            params=condition.get('params', {}) if condition else {},
            enabled=bool(row.get('is_active', 1)),
        )

    def _load_ontology_data(self, ontology_id: str) -> Dict[str, Any]:
        entities = self.storage.get_registry_entities(ontology_id)

        scenarios = self.storage.list_scenarios()
        ontology_scenarios = [s for s in scenarios if s.get('ontology_id') == ontology_id]

        relations = []
        doc_entities = []
        for scenario in ontology_scenarios:
            docs = self.storage.get_scenario_documents(scenario['scenario_id'])
            for doc in docs:
                relations.extend(doc.get('relations', []))
                doc_entities.extend(doc.get('entities', []))

        if not entities and doc_entities:
            seen = set()
            unique = []
            for e in doc_entities:
                eid = e.get('entity_id')
                if eid and eid not in seen:
                    seen.add(eid)
                    unique.append(e)
            entities = unique

        version = self.storage.get_current_version(ontology_id)
        ontology_version = "1.0.0"
        if version:
            ontology_version = version.get('version_number', '1.0.0')

        return {
            'entities': entities,
            'relations': relations,
            'ontology_version': ontology_version,
        }

    def _check_entity_rule(self, rule: ValidationRule, data: Dict[str, Any],
                           ontology_id: str) -> List[ValidationIssue]:
        issues = []
        entities = data.get('entities', [])
        expression = rule.expression
        params = rule.params or {}

        if expression == 'min_count':
            minimum = params.get('min', 1)
            if len(entities) < minimum:
                issues.append(ValidationIssue(
                    rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                    message=f"Entity count {len(entities)} is below minimum {minimum}",
                    details={'actual_count': len(entities), 'required_min': minimum,
                             'auto_fixable': False},
                ))

        elif expression == 'required_type':
            required_type = params.get('entity_type', '')
            found = any(e.get('entity_type') == required_type for e in entities)
            if not found:
                issues.append(ValidationIssue(
                    rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                    message=f"No entity of required type '{required_type}' found",
                    details={'required_type': required_type, 'auto_fixable': False},
                ))

        elif expression == 'naming_convention':
            pattern = params.get('pattern', r'^[A-Za-z0-9_\u4e00-\u9fff]+$')
            for entity in entities:
                name = entity.get('name', '')
                if name and not re.match(pattern, name):
                    issues.append(ValidationIssue(
                        rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                        entity_id=entity.get('canonical_id') or entity.get('entity_id'),
                        message=f"Entity name '{name}' violates naming convention",
                        details={'name': name, 'pattern': pattern, 'auto_fixable': True},
                    ))

        elif expression == 'no_empty_names':
            for entity in entities:
                name = entity.get('name', '')
                if not name or not name.strip():
                    issues.append(ValidationIssue(
                        rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                        entity_id=entity.get('canonical_id') or entity.get('entity_id'),
                        message="Entity has empty name",
                        details={'entity_id': entity.get('canonical_id') or entity.get('entity_id'),
                                 'auto_fixable': False},
                    ))

        elif expression == 'unique_names':
            seen = {}
            for entity in entities:
                name = entity.get('name', '')
                etype = entity.get('entity_type', '')
                key = (etype, name)
                if name and key in seen:
                    issues.append(ValidationIssue(
                        rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                        entity_id=entity.get('canonical_id') or entity.get('entity_id'),
                        message=f"Duplicate entity name '{name}' of type '{etype}'",
                        details={'name': name, 'entity_type': etype,
                                 'first_occurrence': seen[key], 'auto_fixable': False},
                    ))
                else:
                    eid = entity.get('canonical_id') or entity.get('entity_id')
                    seen[key] = eid

        elif expression == 'no_duplicate_ids':
            seen = {}
            for entity in entities:
                eid = entity.get('canonical_id') or entity.get('entity_id')
                if eid and eid in seen:
                    issues.append(ValidationIssue(
                        rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                        entity_id=eid,
                        message=f"Duplicate entity ID '{eid}'",
                        details={'entity_id': eid, 'auto_fixable': False},
                    ))
                elif eid:
                    seen[eid] = True

        return issues

    def _check_relation_rule(self, rule: ValidationRule, data: Dict[str, Any],
                             ontology_id: str) -> List[ValidationIssue]:
        issues = []
        relations = data.get('relations', [])
        entities = data.get('entities', [])
        expression = rule.expression
        params = rule.params or {}

        entity_ids = set()
        for e in entities:
            eid = e.get('canonical_id') or e.get('entity_id')
            if eid:
                entity_ids.add(eid)

        if expression == 'no_orphans':
            for rel in relations:
                source = rel.get('source_entity', '')
                target = rel.get('target_entity', '')
                missing = []
                if source and source not in entity_ids:
                    missing.append(source)
                if target and target not in entity_ids:
                    missing.append(target)
                if missing:
                    issues.append(ValidationIssue(
                        rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                        relation_id=rel.get('relation_id'),
                        message=f"Relation references non-existent entities: {', '.join(missing)}",
                        details={'missing_entities': missing, 'auto_fixable': False},
                    ))

        elif expression == 'no_self_reference':
            for rel in relations:
                source = rel.get('source_entity', '')
                target = rel.get('target_entity', '')
                if source and target and source == target:
                    issues.append(ValidationIssue(
                        rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                        relation_id=rel.get('relation_id'),
                        message=f"Self-referencing relation on entity '{source}'",
                        details={'entity_id': source, 'auto_fixable': True},
                    ))

        elif expression == 'min_count':
            minimum = params.get('min', 1)
            if len(relations) < minimum:
                issues.append(ValidationIssue(
                    rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                    message=f"Relation count {len(relations)} is below minimum {minimum}",
                    details={'actual_count': len(relations), 'required_min': minimum,
                             'auto_fixable': False},
                ))

        elif expression == 'valid_types':
            allowed = set(params.get('allowed_types', []))
            if allowed:
                for rel in relations:
                    rtype = rel.get('relation_type', '')
                    if rtype and rtype not in allowed:
                        issues.append(ValidationIssue(
                            rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                            relation_id=rel.get('relation_id'),
                            message=f"Invalid relation type '{rtype}'",
                            details={'relation_type': rtype,
                                     'allowed_types': sorted(allowed), 'auto_fixable': False},
                        ))

        return issues

    def _check_property_rule(self, rule: ValidationRule, data: Dict[str, Any],
                             ontology_id: str) -> List[ValidationIssue]:
        issues = []
        entities = data.get('entities', [])
        expression = rule.expression
        params = rule.params or {}

        if expression == 'required_property':
            prop_name = params.get('property_name', '')
            entity_type = params.get('entity_type', '')
            for entity in entities:
                if entity_type and entity.get('entity_type') != entity_type:
                    continue
                props = entity.get('basic_properties', {})
                if prop_name and prop_name not in props:
                    issues.append(ValidationIssue(
                        rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                        entity_id=entity.get('canonical_id') or entity.get('entity_id'),
                        property_name=prop_name,
                        message=f"Entity '{entity.get('name', '')}' missing required property '{prop_name}'",
                        details={'property_name': prop_name, 'auto_fixable': False},
                    ))

        elif expression == 'property_type':
            prop_name = params.get('property_name', '')
            expected_type = params.get('expected_type', 'str')
            entity_type = params.get('entity_type', '')
            type_map = {'str': str, 'int': int, 'float': (int, float), 'bool': bool, 'list': list, 'dict': dict}
            expected = type_map.get(expected_type, str)
            for entity in entities:
                if entity_type and entity.get('entity_type') != entity_type:
                    continue
                props = entity.get('basic_properties', {})
                if prop_name in props:
                    val = props[prop_name]
                    if not isinstance(val, expected):
                        issues.append(ValidationIssue(
                            rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
                            entity_id=entity.get('canonical_id') or entity.get('entity_id'),
                            property_name=prop_name,
                            message=f"Property '{prop_name}' has type {type(val).__name__}, expected {expected_type}",
                            details={'property_name': prop_name, 'actual_type': type(val).__name__,
                                     'expected_type': expected_type, 'auto_fixable': False},
                        ))

        return issues

    def validate_ontology(self, ontology_id: str,
                         rules: List[str] = None) -> ValidationResult:
        start_time = datetime.now()

        ontology_data = self._load_ontology_data(ontology_id)

        result = ValidationResult(
            ontology_id=ontology_id,
            ontology_version=ontology_data.get('ontology_version', '1.0.0'),
            status="running",
        )

        if rules:
            validation_rules = []
            for rule_id in rules:
                r = self.get_validation_rule(rule_id)
                if r and r.enabled:
                    validation_rules.append(r)
        else:
            validation_rules = self.list_validation_rules({"enabled": True})

        all_issues = []
        for rule in validation_rules:
            if rule.rule_type == 'entity':
                rule_issues = self._check_entity_rule(rule, ontology_data, ontology_id)
            elif rule.rule_type == 'relation':
                rule_issues = self._check_relation_rule(rule, ontology_data, ontology_id)
            elif rule.rule_type == 'property':
                rule_issues = self._check_property_rule(rule, ontology_data, ontology_id)
            else:
                rule_issues = []
            all_issues.extend(rule_issues)

        errors = []
        warnings = []
        info = []
        now = datetime.now().isoformat()

        for issue in all_issues:
            issue_dict = issue.model_dump()
            issue_dict['ontology_id'] = ontology_id
            issue_dict['auto_fixable'] = issue.details.get('auto_fixable', False)
            issue_dict['status'] = 'open'
            issue_dict['timestamp'] = issue.timestamp.isoformat() if isinstance(issue.timestamp, datetime) else str(issue.timestamp)
            issue_dict['created_at'] = now

            self.storage.save_validation_issue(issue_dict)

            if issue.severity == ValidationSeverity.ERROR:
                errors.append(issue_dict)
            elif issue.severity == ValidationSeverity.WARNING:
                warnings.append(issue_dict)
            else:
                info.append(issue_dict)

        result.status = "complete"
        result.errors = errors
        result.warnings = warnings
        result.info = info
        result.error_count = len(errors)
        result.warning_count = len(warnings)
        result.info_count = len(info)
        total_rules = len(validation_rules) if validation_rules else 1
        result.overall_score = max(0.0, 1.0 - (len(errors) * 0.5 + len(warnings) * 0.2) / total_rules)
        result.duration_seconds = (datetime.now() - start_time).total_seconds()

        result_dict = result.model_dump()
        result_dict['validation_time'] = result.validation_time.isoformat()
        self.storage.save_validation_result(result_dict)

        return result

    def get_validation_result(self, result_id: str) -> Optional[ValidationResult]:
        data = self.storage.get_validation_result(result_id)
        if not data:
            return None
        return ValidationResult(**data) if isinstance(data, dict) else data

    def list_validation_issues(self, ontology_id: str,
                              severity: ValidationSeverity = None,
                              start_time: Optional[str] = None,
                              end_time: Optional[str] = None) -> List[ValidationIssue]:
        severity_val = severity.value if severity else None
        rows = self.storage.list_validation_issues(
            ontology_id=ontology_id,
            severity=severity_val,
            start_time=start_time,
            end_time=end_time,
        )
        issues = []
        for row in rows:
            issues.append(ValidationIssue(
                id=row.get('issue_id', ''),
                rule_id=row.get('rule_id', ''),
                rule_name=row.get('rule_name', ''),
                severity=ValidationSeverity(row.get('severity', 'warning')),
                entity_id=row.get('entity_id'),
                relation_id=row.get('relation_id'),
                property_name=row.get('property_name'),
                message=row.get('message', ''),
                details=row.get('details') or {},
                timestamp=datetime.fromisoformat(row['timestamp']) if row.get('timestamp') else datetime.now(),
            ))
        return issues

    def fix_validation_issue(self, issue_id: str, fix_action: Dict[str, Any]) -> bool:
        issue_row = self.storage.get_validation_issue(issue_id)
        if not issue_row:
            return False

        if issue_row.get('status') == 'fixed':
            return True

        auto_fixable = issue_row.get('auto_fixable', False)
        details = issue_row.get('details') or {}
        rule_name = issue_row.get('rule_name', '')
        entity_id = issue_row.get('entity_id')

        if auto_fixable and entity_id:
            if 'naming_convention' in rule_name or details.get('auto_fixable') is True:
                name = details.get('name', '')
                if name:
                    fixed_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', name).strip('_')
                    if fixed_name:
                        self.storage.update_entity_name(entity_id, fixed_name)
                        self.storage.update_validation_issue(issue_id, {
                            'status': 'fixed',
                            'details': {**details, 'fixed_name': fixed_name, 'original_name': name},
                        })
                        return True

        self.storage.update_validation_issue(issue_id, {
            'status': 'acknowledged',
        })
        return True
