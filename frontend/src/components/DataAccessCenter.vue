<script setup>
import { computed } from 'vue'

const props = defineProps({
  policyPacks: { type: Array, default: () => [] },
  dataSources: { type: Array, default: () => [] },
  selectedPolicyId: { type: String, default: '' },
  selectedDataSourceId: { type: String, default: '' },
  tablePayloadJson: { type: String, default: '' },
  tablePayloadError: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:selectedPolicyId',
  'update:selectedDataSourceId',
  'update:tablePayloadJson',
  'refresh',
  'reset-table-payload',
])

const selectedPolicy = computed(() =>
  props.policyPacks.find((item) => item.policy_id === props.selectedPolicyId) || null
)

const selectedDataSource = computed(() =>
  props.dataSources.find((item) => item.data_source_id === props.selectedDataSourceId) || null
)

const selectedPolicyModel = computed({
  get: () => props.selectedPolicyId,
  set: (value) => emit('update:selectedPolicyId', value),
})

const selectedDataSourceModel = computed({
  get: () => props.selectedDataSourceId,
  set: (value) => emit('update:selectedDataSourceId', value),
})

const tablePayloadModel = computed({
  get: () => props.tablePayloadJson,
  set: (value) => emit('update:tablePayloadJson', value),
})

const policyStats = computed(() => ({
  total: props.policyPacks.length,
  selected: selectedPolicy.value?.policy_name || '未选择',
}))

const dataSourceStats = computed(() => ({
  total: props.dataSources.length,
  selected: selectedDataSource.value?.display_name || selectedDataSource.value?.data_source_id || '未选择',
}))

const isTablePayloadSource = computed(() => {
  const source = selectedDataSource.value
  return props.selectedDataSourceId === 'table_payload_demo' || source?.type === 'table_payload'
})

const policyLabel = (policy) => policy.policy_name || policy.policy_id
const sourceLabel = (source) => source.display_name || source.data_source_id
</script>

<template>
  <div class="data-access-center">
    <div class="access-hero">
      <div>
        <div class="access-eyebrow">可插拔资源配置</div>
        <h2>数据接入</h2>
        <p>统一查看并选择政策库与业务数据库，审查流程会按这里的当前选择启动取证。</p>
      </div>
      <div class="access-actions">
        <el-button :loading="loading" :disabled="loading" plain @click="emit('refresh')">刷新目录</el-button>
      </div>
    </div>

    <div class="access-summary-grid">
      <div class="summary-tile">
        <span>政策库</span>
        <strong>{{ policyStats.total }}</strong>
        <small>{{ policyStats.selected }}</small>
      </div>
      <div class="summary-tile">
        <span>业务数据库</span>
        <strong>{{ dataSourceStats.total }}</strong>
        <small>{{ dataSourceStats.selected }}</small>
      </div>
      <div class="summary-tile">
        <span>当前链路</span>
        <strong>{{ selectedPolicyId ? '已配置' : '待选择' }}</strong>
        <small>{{ selectedDataSourceId || '未选择数据源' }}</small>
      </div>
    </div>

    <div class="access-grid">
      <section class="access-panel">
        <div class="panel-head">
          <div>
            <h3>政策库</h3>
            <p>政策包声明审核规则、证据需求、提示词与报告模板。</p>
          </div>
          <el-tag effect="plain">{{ policyPacks.length }} 个政策包</el-tag>
        </div>

        <el-select
          v-model="selectedPolicyModel"
          :disabled="disabled"
          filterable
          class="access-select"
          placeholder="选择当前政策包"
        >
          <el-option
            v-for="policy in policyPacks"
            :key="policy.policy_id"
            :label="policyLabel(policy)"
            :value="policy.policy_id"
          />
        </el-select>

        <div v-if="selectedPolicy" class="detail-card detail-card--selected">
          <div class="detail-title">{{ selectedPolicy.policy_name }}</div>
          <div class="detail-meta">
            <el-tag size="small" effect="plain">{{ selectedPolicy.policy_id }}</el-tag>
            <el-tag v-if="selectedPolicy.version" size="small" effect="plain">v{{ selectedPolicy.version }}</el-tag>
            <el-tag v-if="selectedPolicy.default_data_source_id" size="small" type="info" effect="plain">
              默认数据源 {{ selectedPolicy.default_data_source_id }}
            </el-tag>
          </div>
          <p>{{ selectedPolicy.description || '暂无政策描述。' }}</p>
        </div>

        <div class="resource-list">
          <div
            v-for="policy in policyPacks"
            :key="policy.policy_id"
            class="resource-row"
            :class="{ 'resource-row--active': policy.policy_id === selectedPolicyId }"
            @click="!disabled && emit('update:selectedPolicyId', policy.policy_id)"
          >
            <div>
              <div class="resource-name">{{ policy.policy_name }}</div>
              <div class="resource-desc">{{ policy.description || policy.pack_id || policy.policy_id }}</div>
            </div>
            <el-tag size="small" effect="plain">{{ policy.policy_id }}</el-tag>
          </div>
        </div>
      </section>

      <section class="access-panel">
        <div class="panel-head">
          <div>
            <h3>业务数据库</h3>
            <p>数据源包声明连接引用、实体映射和可用采集器。</p>
          </div>
          <el-tag effect="plain">{{ dataSources.length }} 个数据源</el-tag>
        </div>

        <el-select
          v-model="selectedDataSourceModel"
          :disabled="disabled"
          filterable
          class="access-select"
          placeholder="选择当前数据源包"
        >
          <el-option
            v-for="source in dataSources"
            :key="source.data_source_id"
            :label="sourceLabel(source)"
            :value="source.data_source_id"
          >
            <span>{{ sourceLabel(source) }}</span>
            <span class="option-meta">{{ source.type }}</span>
          </el-option>
        </el-select>

        <div v-if="selectedDataSource" class="detail-card detail-card--selected">
          <div class="detail-title">{{ sourceLabel(selectedDataSource) }}</div>
          <div class="detail-meta">
            <el-tag size="small" effect="plain">{{ selectedDataSource.data_source_id }}</el-tag>
            <el-tag size="small" type="success" effect="plain">{{ selectedDataSource.type }}</el-tag>
            <el-tag v-if="selectedDataSource.connection_ref" size="small" type="info" effect="plain">
              {{ selectedDataSource.connection_ref }}
            </el-tag>
          </div>
          <p>{{ selectedDataSource.description || '暂无数据源描述。' }}</p>
        </div>

        <div class="resource-list">
          <div
            v-for="source in dataSources"
            :key="source.data_source_id"
            class="resource-row"
            :class="{ 'resource-row--active': source.data_source_id === selectedDataSourceId }"
            @click="!disabled && emit('update:selectedDataSourceId', source.data_source_id)"
          >
            <div>
              <div class="resource-name">{{ sourceLabel(source) }}</div>
              <div class="resource-desc">{{ source.description || source.data_source_id }}</div>
            </div>
            <el-tag size="small" effect="plain">{{ source.type }}</el-tag>
          </div>
        </div>
      </section>
    </div>

    <section v-if="isTablePayloadSource" class="access-panel table-payload-panel">
      <div class="panel-head">
        <div>
          <h3>表格材料直传</h3>
          <p>当前数据源支持通过 records 或 tables 传入结构化材料，并转换为证据卡片。</p>
        </div>
        <el-button size="small" plain :disabled="disabled" @click="emit('reset-table-payload')">重置示例</el-button>
      </div>
      <el-input
        v-model="tablePayloadModel"
        :disabled="disabled"
        type="textarea"
        :rows="9"
        spellcheck="false"
        class="table-payload-input"
      />
      <el-alert
        v-if="tablePayloadError"
        type="error"
        :closable="false"
        show-icon
        class="table-payload-error"
      >
        {{ tablePayloadError }}
      </el-alert>
    </section>
  </div>
</template>

<style scoped>
.data-access-center {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 32px 40px;
  color: var(--color-text-main);
}

.access-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
  border: 1px solid var(--border-color);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(36, 52, 71, 0.06);
}

.access-eyebrow {
  color: var(--color-primary-red);
  font-size: 13px;
  font-weight: 700;
}

.access-hero h2 {
  margin: 6px 0 8px;
  font-size: 28px;
  letter-spacing: 0;
}

.access-hero p,
.panel-head p,
.detail-card p,
.resource-desc {
  margin: 0;
  color: var(--color-text-secondary);
  line-height: 1.65;
}

.access-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 16px 0;
}

.summary-tile,
.access-panel,
.detail-card,
.resource-row {
  border: 1px solid var(--border-color);
  background: #fff;
}

.summary-tile {
  padding: 18px;
  border-radius: 10px;
}

.summary-tile span,
.summary-tile small {
  display: block;
  color: var(--color-text-secondary);
}

.summary-tile strong {
  display: block;
  margin: 8px 0 4px;
  font-size: 26px;
  letter-spacing: 0;
}

.access-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.access-panel {
  padding: 20px;
  border-radius: 12px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-head h3 {
  margin: 0 0 6px;
  font-size: 19px;
  letter-spacing: 0;
}

.access-select {
  width: 100%;
  margin-bottom: 14px;
}

.option-meta {
  float: right;
  color: #8a98aa;
  font-size: 12px;
}

.detail-card {
  padding: 14px;
  border-radius: 10px;
  margin-bottom: 14px;
}

.detail-card--selected {
  border-color: rgba(159, 29, 34, 0.22);
  background: #fffafa;
}

.detail-title {
  font-weight: 700;
  margin-bottom: 8px;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.resource-list {
  display: grid;
  gap: 10px;
  max-height: 360px;
  overflow: auto;
  padding-right: 4px;
}

.resource-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-radius: 9px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.resource-row:hover,
.resource-row--active {
  border-color: rgba(159, 29, 34, 0.28);
  background: #fff7f6;
}

.resource-name {
  font-weight: 700;
  margin-bottom: 4px;
}

.table-payload-panel {
  margin-top: 16px;
}

.table-payload-input {
  font-family: Consolas, 'Courier New', monospace;
}

.table-payload-error {
  margin-top: 10px;
}

@media (max-width: 1100px) {
  .data-access-center {
    padding: 16px;
  }

  .access-hero,
  .panel-head {
    flex-direction: column;
  }

  .access-summary-grid,
  .access-grid {
    grid-template-columns: 1fr;
  }
}
</style>
