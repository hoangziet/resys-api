# Tài liệu API

Base URL: `http://localhost:8000/api/v1`

Tất cả endpoint (trừ auth) yêu cầu header `Authorization: Bearer <token>`.

---

## Auth

### POST /auth/register

Đăng ký tài khoản mới.

**Request:**
```json
{
    "username": "john",
    "password": "Secure123"
}
```

**Response `200`:**
```json
{
    "status": "ok",
    "message": "User registered successfully"
}
```

**Errors:**

| Status | Mô tả |
|--------|-------|
| `400` | Username đã tồn tại hoặc password không đủ mạnh |
| `429` | Vượt quá rate limit (5/phút) |

---

### POST /auth/token

Đăng nhập, trả về JWT token. Gửi dạng `application/x-www-form-urlencoded`.

**Request:**
```
username=john&password=Secure123
```

**Response `200`:**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
}
```

**Errors:**

| Status | Mô tả |
|--------|-------|
| `401` | Sai username hoặc password |
| `429` | Vượt quá rate limit (10/phút) |

---

### GET /auth/me

Lấy thông tin người dùng hiện tại.

**Response `200`:**
```json
{
    "username": "john",
    "role": "learner"
}
```

---

## History

### GET /history/

Lấy lịch sử học tập.

**Response `200`:**
```json
{
    "user": "john",
    "history": [
        {
            "item_idx": 42,
            "item_id": "course_123",
            "title": "Introduction to Python",
            "description": "...",
            "language": "fr",
            "difficulty": "beginner",
            "theme": "Programming",
            "type": "Course",
            "duration": 3600.0,
            "thumbnail_url": "/assets/thumbnail.png",
            "video_url": "/assets/video.mp4"
        }
    ]
}
```

---

### POST /history/?item_idx={item_idx}

Thêm khóa học vào lịch sử.

**Response `200`:**
```json
{
    "user": "john",
    "item_idx": 42,
    "status": "added"
}
```

**Errors:**

| Status | Mô tả |
|--------|-------|
| `404` | Không tìm thấy course với item_idx này |
| `500` | Lỗi server khi thêm vào database |

---

### DELETE /history/{item_idx}

Xóa một khóa học khỏi lịch sử.

**Response `200`:**
```json
{
    "user": "john",
    "item_idx": 42,
    "status": "removed"
}
```

---

### DELETE /history/

Xóa toàn bộ lịch sử học tập.

**Response `200`:**
```json
{
    "user": "john",
    "status": "cleared"
}
```

---

## Courses

### GET /courses/

Tìm kiếm khóa học. Hỗ trợ query parameter `q` cho search.

**Response `200`:**
```json
{
    "data": [
        {
            "item_idx": 42,
            "title": "Introduction to Python",
            "description": "...",
            "language": "fr",
            "difficulty": "beginner",
            "theme": "Programming",
            "type": "Course",
            "software": "Python",
            "job": "Developer",
            "duration": 3600.0,
            "thumbnail_url": "/assets/thumbnail.png"
        }
    ]
}
```

---

### GET /courses/{course_id}

Lấy chi tiết một khóa học.

**Response `200`:**
```json
{
    "item_idx": 42,
    "title": "Introduction to Python",
    "description": "...",
    "language": "fr",
    "difficulty": "beginner",
    "theme": "Programming",
    "type": "Course",
    "software": "Python",
    "job": "Developer",
    "duration": 3600.0,
    "thumbnail_url": "/assets/thumbnail.png",
    "video_url": "/assets/video.mp4"
}
```

**Errors:**

| Status | Mô tả |
|--------|-------|
| `404` | Không tìm thấy khóa học |

---

## Recommendations

### POST /recommendations/for-you

Gợi ý cá nhân hóa dựa trên lịch sử (BERT4Rec).

**Request:**
```json
{
    "history": [1, 2, 3],
    "limit": 10
}
```

`history` có thể truyền từ client hoặc server sẽ tự lấy từ DB. `limit` từ 1 đến 50, mặc định 10.

**Response `200`:**
```json
{
    "source": "bert4rec_personalized",
    "items": [
        {
            "rank": 1,
            "item_idx": 87,
            "score": 0.35
        }
    ],
    "limit": 10,
    "latency_ms": 12.5
}
```

**Fallback:** Nếu model gặp lỗi, trả về khóa học phổ biến với `source: "popular_fallback_error"`.

**Rate limit:** 5/giây.

---

### POST /recommendations/you-may-also-like

Gợi ý tương đồng dựa trên khóa học cuối cùng trong lịch sử.

**Request:**
```json
{
    "limit": 10
}
```

**Response `200`:**
```json
{
    "source": "vector_similarity",
    "anchor_item_idx": 42,
    "items": [
        {
            "item_idx": 87,
            "title": "...",
            "score": 0.92
        }
    ],
    "limit": 10,
    "latency_ms": 5.3
}
```

---

### POST /recommendations/popular

Lấy khóa học phổ biến.

**Response `200`:**
```json
{
    "source": "popular",
    "items": [...],
    "limit": 10,
    "latency_ms": 1.2
}
```

---

### POST /recommendations/similar/{course_id}

Gợi ý tương tự cho một khóa học cụ thể.

**Response `200`:**
```json
{
    "source": "vector_similarity",
    "course_id": 42,
    "items": [...],
    "limit": 10,
    "latency_ms": 5.1
}
```

---

## Admin (yêu cầu role admin)

### GET /admin/model-health

Kiểm tra trạng thái model.

**Response `200`:**
```json
{
    "status": "healthy",
    "artifact": "bert4rec.pt",
    "vocab_size": 3240,
    "max_len": 50,
    "hidden_dim": 64
}
```

---

### GET /admin/recommendation-logs

Lấy log gợi ý gần nhất (100 bản ghi).

**Response `200`:**
```json
{
    "logs": [
        {
            "id": 1,
            "timestamp": "2026-07-26 16:00:00",
            "username": "john",
            "strategy": "bert4rec_personalized",
            "latency_ms": 12.5,
            "history": "1,2,3",
            "results": "87,42,15"
        }
    ]
}
```

---

### POST /admin/cleanup-logs

Xóa log hết hạn (dựa trên `LOG_RETENTION_DAYS`).

**Response `200`:**
```json
{
    "deleted": 42,
    "retention_days": 30
}
```

---

### POST /admin/sync-catalog

Đồng bộ catalog (stub — chưa implement đầy đủ).

---

### POST /admin/rebuild-embeddings

Tạo lại embeddings (stub — chưa implement đầy đủ).

---

## Debug (chỉ development mode)

### GET /debug/infer

Test inference với history cứng. Trả `404` ở production.

**Response `200`:**
```json
{
    "recommendations": [...],
    "model_loaded": true,
    "device": "cuda"
}
```
