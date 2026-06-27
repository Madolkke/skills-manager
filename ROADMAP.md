# 后端重构路线图

本文档记录 SkillHub 后端的目标架构。当前重构不以小修小补为目标，而是围绕现有业务重新建立清晰的 Python Web 应用结构。

## 1. 重构目标

目标：将后端整理为“业务域 + Clean Architecture / Hexagonal Architecture”的结构，让 Skill、Bundle、Version、Evaluation、History、Saved View、Workflow 等能力拥有清晰边界。

核心原则：

- `main.py` 只保留启动入口。
- `bootstrap/` 负责应用装配、配置、数据库、中间件、异常处理和路由注册。
- 每个业务域独立维护自己的 `domain`、`application`、`infrastructure`、`api`。
- `domain` 不依赖 FastAPI、SQLAlchemy、Pydantic。
- `application` 只承载用例编排。
- `infrastructure` 负责数据库、存储和外部系统适配。
- `api` 只处理 HTTP 路由、请求 schema 和响应 schema。
- 测试目录按业务域和测试层级组织。

## 2. 目标目录结构

```text
apps/backend/
  pyproject.toml
  src/
    skillhub/
      __init__.py
      main.py

      bootstrap/
        app.py
        container.py
        database.py
        exceptions.py
        middleware.py
        settings.py

      shared/
        domain/
          errors.py
          events.py
          ids.py
          pagination.py
          permissions.py
          time.py
        application/
          unit_of_work.py
          transaction.py
        infrastructure/
          sqlalchemy/
            engine.py
            metadata.py
            types.py
            unit_of_work.py
          logging.py
        api/
          responses.py
          schemas.py
          dependencies.py

      skills/
        domain/
          models.py
          services.py
          policies.py
          events.py
          errors.py
        application/
          commands.py
          queries.py
          use_cases/
            create_skill.py
            import_skill_bundle.py
            update_skill_metadata.py
            archive_skill.py
            publish_skill_version.py
        infrastructure/
          sqlalchemy/
            tables.py
            repository.py
            queries.py
        api/
          routes.py
          schemas.py

      bundles/
        domain/
          models.py
          diff.py
          validation.py
          errors.py
        application/
          use_cases/
            validate_bundle.py
            compare_bundles.py
            edit_bundle_file.py
            export_bundle.py
        infrastructure/
          storage.py
          sqlalchemy/
            tables.py
            repository.py
        api/
          routes.py
          schemas.py

      versions/
        domain/
          models.py
          policies.py
          errors.py
        application/
          use_cases/
            create_version.py
            compare_versions.py
            set_current_version.py
            get_version_history.py
        infrastructure/
          sqlalchemy/
            tables.py
            repository.py
        api/
          routes.py
          schemas.py

      evaluations/
        domain/
          models.py
          scoring.py
          policies.py
          errors.py
        application/
          use_cases/
            create_eval_set.py
            update_eval_case.py
            run_evaluation.py
            record_result.py
            compare_runs.py
            build_run_matrix.py
        infrastructure/
          sqlalchemy/
            tables.py
            repository.py
            queries.py
        api/
          routes.py
          schemas.py

      evidence/
        domain/
          models.py
          errors.py
        application/
          use_cases/
            attach_artifact.py
            list_artifacts.py
            get_run_evidence.py
        infrastructure/
          storage.py
          sqlalchemy/
            tables.py
            repository.py
        api/
          routes.py
          schemas.py

      history/
        domain/
          models.py
        application/
          use_cases/
            list_skill_history.py
            list_case_history.py
            list_run_history.py
        infrastructure/
          sqlalchemy/
            queries.py
        api/
          routes.py
          schemas.py

      saved_views/
        domain/
          models.py
          errors.py
        application/
          use_cases/
            create_saved_view.py
            update_saved_view.py
            delete_saved_view.py
            list_saved_views.py
        infrastructure/
          sqlalchemy/
            tables.py
            repository.py
        api/
          routes.py
          schemas.py

      workflows/
        domain/
          models.py
          publication.py
          errors.py
        application/
          use_cases/
            publish_workflow_as_skill.py
            validate_workflow_bundle.py
        infrastructure/
          adapters/
            workflow_runtime.py
        api/
          routes.py
          schemas.py

  tests/
    unit/
      skills/
      bundles/
      versions/
      evaluations/
      workflows/
    integration/
      api/
      repositories/
    fakes/
      repositories.py
      storage.py
```

## 3. 业务域边界

`skills` 负责 Skill 本体、slug、owner、生命周期、归档、权限策略和当前版本指针。

`bundles` 负责 Skill 内容包、manifest、文件内容、校验、diff、导入导出和在线编辑。

`versions` 负责 Skill 版本、版本名称、变更摘要、当前版本切换、版本历史和版本对比。

`evaluations` 负责评测集、测试用例、评测运行、评分、run matrix 和运行结果对比。

`evidence` 负责运行证据、附件、日志、截图和运行产物。

`history` 负责审计事件、Skill 历史、Case 历史、Run 历史和 bundle audit 查询。

`saved_views` 负责保存视图、筛选条件、表格布局和查询偏好。

`workflows` 负责工作流定义、工作流校验、Workflow 到 Skill Bundle 的转换和发布。

## 4. 分阶段执行计划

### 阶段一：启动装配整理

目标：无行为变化地降低入口复杂度。

任务：

- 新增 `skillhub/bootstrap/`。
- 将 FastAPI app factory 移入 `bootstrap/app.py`。
- 将 CORS 配置移入 `bootstrap/middleware.py`。
- 将异常处理注册移入 `bootstrap/exceptions.py`。
- 启动入口统一为 `skillhub.bootstrap.app:create_app`，不再保留旧 `skillhub/api/main.py`。
- 跑完后端测试。

### 阶段二：API 路由重组

目标：把 `routes_core.py`、`routes_commands.py`、`routes_history.py` 从技术分类迁移到资源分类。

任务：

- 当前路由统一位于 `skillhub/views/`。
- 拆分为 `system.py`、`session.py`、`skills.py`、`versions.py`、`evaluations.py`、`saved_views.py`、`artifacts.py`。
- 保持 URL 与响应格式不变。
- 删除旧的 routes 文件。

### 阶段三：Repository 重组

目标：消除 `repository_parts/` 的碎片化结构。

任务：

- 按业务域拆成 `skills`、`bundles`、`versions`、`evaluations`、`history`、`saved_views` repository。
- 将通用 SQL helper 移入 `shared/infrastructure/sqlalchemy/`。
- 引入 Unit of Work，逐步替代全局 `SqlSkillRepository`。
- 保持外部 API 行为不变。

### 阶段四：Domain / Application 边界整理

目标：让业务规则离开 API 和 repository。

任务：

- 将 Skill 创建、导入、归档、版本发布迁移为 use case。
- 将评测运行、结果记录、run matrix、run comparison 迁移为 use case。
- 将 bundle 校验、bundle diff、bundle export 迁移到 `bundles` 域。
- 补充 domain unit tests。

### 阶段五：测试结构重排

目标：测试目录镜像业务结构。

任务：

- 拆分 `tests/unit/`、`tests/integration/`、`tests/fakes/`。
- API contract 测试放入 `tests/integration/api/`。
- repository 测试放入 `tests/integration/repositories/`。
- domain 和 use case 测试放入 `tests/unit/`。

## 5. 完成标准

- `main.py` 保持极薄，只导入并暴露 `create_app()` 与 `app`。
- 不再新增全局 `routes_*.py`。
- 不再新增 `repository_parts/*`。
- 每个新业务能力必须归属到明确业务域。
- 当前开发阶段不启用 Alembic migration 流程，数据库由启动时 schema 初始化和兼容逻辑管理。
- 后端测试、前端 lint/build 在每轮重构后通过。
