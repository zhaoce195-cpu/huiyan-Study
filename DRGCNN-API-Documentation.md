# DRGCNN API 使用文档

## 概述

DRGCNN API 是一个基于深度学习的糖尿病视网膜病变（Diabetic Retinopathy, DR）双眼检测系统。通过输入左右眼的眼底图像，API 会返回病变等级预测结果和 GradCAM 热力图可视化。

**基础URL**: `http://113.219.243.122:9050`

---

## API 端点

### 1. 首页

**端点**: `GET /`

**描述**: 返回 API 欢迎信息

**响应示例**:
```
Welcome to the Predict API. Use /predict_twoeyes to make predictions.
```

---

### 2. 双眼预测 (核心功能)

**端点**: `POST /predict_twoeyes`

**描述**: 提交左右眼图像进行 DR 病变等级预测，返回预测结果和热力图

**请求格式**: `Content-Type: application/json`

**请求参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| leftUrl | string | 是 | 左眼图像，支持三种格式：<br>1. HTTP/HTTPS URL<br>2. 本地文件路径<br>3. Base64 编码 (data:image/...;base64,...) |
| rightUrl | string | 是 | 右眼图像，格式同 leftUrl |

**请求示例**:
```json
{
  "leftUrl": "https://example.com/left_eye.jpeg",
  "rightUrl": "https://example.com/right_eye.jpeg"
}
```

或使用 Base64:
```json
{
  "leftUrl": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "rightUrl": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

**响应格式**:
```json
{
  "left_eye_prediction": 2,
  "right_eye_prediction": 1,
  "left_eye_probability": 2.134,
  "right_eye_probability": 1.023,
  "left_eye_image_name": "left_image.jpeg",
  "right_eye_image_name": "right_image.jpeg",
  "left_eye_heatmap_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "right_eye_heatmap_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

**响应字段说明**:
| 字段 | 类型 | 说明 |
|------|------|------|
| left_eye_prediction | int | 左眼病变等级 (0-4) |
| right_eye_prediction | int | 右眼病变等级 (0-4) |
| left_eye_probability | float | 左眼预测回归值 |
| right_eye_probability | float | 右眼预测回归值 |
| left_eye_image_name | string | 左眼图像文件名 |
| right_eye_image_name | string | 右眼图像文件名 |
| left_eye_heatmap_base64 | string | 左眼热力图 Base64 编码 |
| right_eye_heatmap_base64 | string | 右眼热力图 Base64 编码 |

**病变等级说明**:
- **0**: 无病变 (No DR)
- **1**: 轻度非增殖性病变 (Mild NPDR)
- **2**: 中度非增殖性病变 (Moderate NPDR)
- **3**: 重度非增殖性病变 (Severe NPDR)
- **4**: 增殖性病变 (PDR)

**错误响应**:
```json
{
  "error": "错误描述信息"
}
```

**HTTP 状态码**:
- `200`: 成功
- `400`: 请求参数错误
- `404`: 文件未找到
- `500`: 服务器内部错误

---

### 3. 获取数据集病变等级列表

**端点**: `GET /dataset/grades`

**描述**: 获取测试数据集中所有病变等级及对应图片数量

**响应示例**:
```json
{
  "grades": [
    {"grade": "0", "count": 150},
    {"grade": "1", "count": 120},
    {"grade": "2", "count": 180},
    {"grade": "3", "count": 90},
    {"grade": "4", "count": 60}
  ],
  "path": "/home/alex/ditu/csu-eyes/EyePACS/eyepacs(origin)/test/test"
}
```

---

### 4. 获取指定等级的患者列表

**端点**: `GET /dataset/images/<grade>`

**描述**: 获取指定病变等级的患者双眼图像列表（分页）

**路径参数**:
- `grade`: 病变等级 (0-4)

**查询参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| limit | int | 20 | 每页数量 |

**请求示例**:
```
GET /dataset/images/2?page=1&limit=10
```

**响应示例**:
```json
{
  "grade": "2",
  "total": 180,
  "page": 1,
  "limit": 10,
  "patients": [
    {
      "id": "10076",
      "left": "10076_left.jpeg",
      "right": "10076_right.jpeg"
    },
    {
      "id": "10234",
      "left": "10234_left.jpeg",
      "right": "10234_right.jpeg"
    }
  ]
}
```

---

### 5. 获取图像文件

**端点**: `GET /dataset/image/<grade>/<filename>`

**描述**: 获取指定病变等级的图像文件（返回 JPEG 文件）

**路径参数**:
- `grade`: 病变等级 (0-4)
- `filename`: 图像文件名

**请求示例**:
```
GET /dataset/image/2/10076_left.jpeg
```

**响应**: 返回图像文件 (MIME type: image/jpeg)

---

### 6. 获取图像 Base64 编码

**端点**: `GET /dataset/image_base64/<grade>/<filename>`

**描述**: 获取图像的 Base64 编码（JSON 格式）

**路径参数**:
- `grade`: 病变等级 (0-4)
- `filename`: 图像文件名

**请求示例**:
```
GET /dataset/image_base64/2/10076_left.jpeg
```

**响应示例**:
```json
{
  "filename": "10076_left.jpeg",
  "grade": "2",
  "base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

---

## 完整使用示例

### Python 示例

```python
import requests
import json

# API 基础 URL
BASE_URL = "http://113.219.243.122:9050"

# 示例 1: 使用 URL 进行预测
def predict_with_urls():
    url = f"{BASE_URL}/predict_twoeyes"
    payload = {
        "leftUrl": "https://example.com/left_eye.jpeg",
        "rightUrl": "https://example.com/right_eye.jpeg"
    }

    response = requests.post(url, json=payload)
    result = response.json()

    print(f"左眼预测等级: {result['left_eye_prediction']}")
    print(f"右眼预测等级: {result['right_eye_prediction']}")
    print(f"左眼回归值: {result['left_eye_probability']}")
    print(f"右眼回归值: {result['right_eye_probability']}")

# 示例 2: 使用数据集图像进行预测
def predict_with_dataset():
    # 获取病变等级为 2 的患者列表
    response = requests.get(f"{BASE_URL}/dataset/images/2?page=1&limit=1")
    data = response.json()

    if data['patients']:
        patient = data['patients'][0]
        grade = data['grade']

        # 获取左右眼图像的 Base64 编码
        left_response = requests.get(
            f"{BASE_URL}/dataset/image_base64/{grade}/{patient['left']}"
        )
        right_response = requests.get(
            f"{BASE_URL}/dataset/image_base64/{grade}/{patient['right']}"
        )

        left_base64 = left_response.json()['base64']
        right_base64 = right_response.json()['base64']

        # 进行预测
        predict_response = requests.post(
            f"{BASE_URL}/predict_twoeyes",
            json={
                "leftUrl": left_base64,
                "rightUrl": right_base64
            }
        )

        result = predict_response.json()
        print(f"患者 ID: {patient['id']}")
        print(f"真实等级: {grade}")
        print(f"左眼预测: {result['left_eye_prediction']}")
        print(f"右眼预测: {result['right_eye_prediction']}")

# 示例 3: 获取所有病变等级统计
def get_dataset_stats():
    response = requests.get(f"{BASE_URL}/dataset/grades")
    data = response.json()

    print("数据集病变等级统计:")
    for grade_info in data['grades']:
        print(f"等级 {grade_info['grade']}: {grade_info['count']} 张图片")

if __name__ == "__main__":
    predict_with_urls()
    # predict_with_dataset()
    # get_dataset_stats()
```

### JavaScript (Fetch API) 示例

```javascript
const BASE_URL = "http://113.219.243.122:9050";

// 使用 Base64 进行预测
async function predictWithBase64(leftBase64, rightBase64) {
    const response = await fetch(`${BASE_URL}/predict_twoeyes`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            leftUrl: leftBase64,
            rightUrl: rightBase64
        })
    });

    const result = await response.json();

    console.log('左眼预测等级:', result.left_eye_prediction);
    console.log('右眼预测等级:', result.right_eye_prediction);
    console.log('左眼热力图:', result.left_eye_heatmap_base64);
    console.log('右眼热力图:', result.right_eye_heatmap_base64);

    return result;
}

// 获取数据集图像并预测
async function predictFromDataset() {
    // 获取等级 2 的患者
    const patientsResponse = await fetch(
        `${BASE_URL}/dataset/images/2?page=1&limit=1`
    );
    const patientsData = await patientsResponse.json();

    if (patientsData.patients.length > 0) {
        const patient = patientsData.patients[0];
        const grade = patientsData.grade;

        // 获取图像 Base64
        const leftResponse = await fetch(
            `${BASE_URL}/dataset/image_base64/${grade}/${patient.left}`
        );
        const rightResponse = await fetch(
            `${BASE_URL}/dataset/image_base64/${grade}/${patient.right}`
        );

        const leftData = await leftResponse.json();
        const rightData = await rightResponse.json();

        // 进行预测
        const result = await predictWithBase64(
            leftData.base64,
            rightData.base64
        );

        console.log('预测完成:', result);
    }
}
```

### cURL 示例

```bash
# 使用 URL 进行预测
curl -X POST http://113.219.243.122:9050/predict_twoeyes \
  -H "Content-Type: application/json" \
  -d '{
    "leftUrl": "https://example.com/left_eye.jpeg",
    "rightUrl": "https://example.com/right_eye.jpeg"
  }'

# 获取病变等级列表
curl http://113.219.243.122:9050/dataset/grades

# 获取等级 2 的患者列表
curl "http://113.219.243.122:9050/dataset/images/2?page=1&limit=10"

# 下载图像文件
curl http://113.219.243.122:9050/dataset/image/2/10076_left.jpeg \
  -o left_eye.jpeg
```

---

## 注意事项

1. **图像格式**: 支持 JPEG 格式的眼底图像
2. **图像质量**: 建议使用高质量眼底图像以获得更准确的预测结果
3. **处理时间**: 每次预测大约需要 3-10 秒（取决于服务器性能和图像大小）
4. **Base64 编码**: 适用于前端直接展示热力图结果
5. **CORS**: API 已启用 CORS，支持跨域请求
6. **超时设置**: URL 图像加载超时为 20 秒

---

## 技术栈

- **框架**: Flask + Flask-CORS
- **深度学习**: PyTorch
- **模型架构**: EfficientNet V2 + Fusion Model
- **可视化**: GradCAM

---

## 联系方式

如有问题或建议，请联系开发团队。
