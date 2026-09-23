<script setup lang="ts">
import { ref } from 'vue'
import type { UploadFile } from 'element-plus'
import { ElMessage } from 'element-plus'
import { CaseBrowseApi } from '@/api'

const emit = defineEmits<{ imported: [] }>()

const visible = ref(false)
const checking = ref(false)
const committing = ref(false)
const sheet = ref<File | null>(null)
const images = ref<File[]>([])
const report = ref<CaseBrowseApi.CaseImportReport | null>(null)

const naming =
  '影像文件名必须是「登记号_右眼」「登记号_左眼」或「登记号_双眼」，也可以用 _OD / _OS / _OU。眼别列要和文件名一致。左右眼都有时，眼别填「左右眼」，并各传一张。登记表不要出现姓名、手机号、身份证号。'

const open = () => {
  sheet.value = null
  images.value = []
  report.value = null
  visible.value = true
}

const onSheet = (file: UploadFile) => {
  sheet.value = (file.raw as File) || null
  report.value = null
}

const onSheetRemove = () => {
  sheet.value = null
  report.value = null
}

const onImages = (_file: UploadFile, fileList: UploadFile[]) => {
  images.value = fileList.map((item) => item.raw).filter((item): item is File => !!item)
  report.value = null
}

const onCheck = async () => {
  if (!sheet.value) {
    ElMessage.warning('请先选择登记表')
    return
  }
  if (images.value.length === 0) {
    ElMessage.warning('请按命名要求选择影像')
    return
  }
  checking.value = true
  try {
    report.value = await CaseBrowseApi.checkCaseImport(sheet.value, images.value)
  } finally {
    checking.value = false
  }
}

const onCommit = async () => {
  if (!report.value?.token || !report.value.passed) return
  committing.value = true
  try {
    await CaseBrowseApi.commitCaseImport(report.value.token)
    visible.value = false
    emit('imported')
  } finally {
    committing.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <el-dialog v-model="visible" title="批量导入病例" width="760px" destroy-on-close>
    <p class="naming">{{ naming }}</p>
    <div class="actions">
      <el-button @click="CaseBrowseApi.downloadImportTemplate()">下载登记表</el-button>
    </div>
    <div class="pickers">
      <el-upload
        :auto-upload="false"
        :limit="1"
        accept=".csv"
        :on-change="onSheet"
        :on-remove="onSheetRemove"
      >
        <el-button>选择登记表（CSV）</el-button>
      </el-upload>
      <el-upload
        :auto-upload="false"
        multiple
        accept=".jpg,.jpeg,.png,.webp,.bmp"
        :on-change="onImages"
        :on-remove="onImages"
      >
        <el-button>选择影像</el-button>
      </el-upload>
    </div>
    <p v-if="sheet || images.length" class="picked">
      {{ sheet ? sheet.name : '还没有登记表' }}，影像 {{ images.length }} 张
    </p>
    <el-button type="primary" :loading="checking" @click="onCheck">入库前检查</el-button>

    <el-table v-if="report" :data="report.rows" size="small" class="result">
      <el-table-column prop="registerNo" label="登记号" width="120" />
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.ok ? 'success' : 'danger'" size="small">
            {{ row.ok ? '通过' : '不能入库' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="检查说明" min-width="220">
        <template #default="{ row }">
          {{ row.ok ? '左右眼、质量、重复和患者信息均通过' : row.issues.join('；') }}
        </template>
      </el-table-column>
    </el-table>
    <p v-if="report" class="summary">
      共 {{ report.total }} 例，通过 {{ report.passed }} 例，未通过 {{ report.failed }} 例。通过的会以未发布草稿入库，学员暂时看不到。
    </p>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button
        type="primary"
        :disabled="!report?.passed"
        :loading="committing"
        @click="onCommit"
      >
        导入通过的病例
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.naming {
  margin: 0 0 12px;
  line-height: 1.6;
  color: #1d2129;
}
.actions,
.pickers {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}
.picked,
.summary {
  color: #4e5969;
  font-size: 13px;
}
.result {
  margin-top: 12px;
}
</style>
