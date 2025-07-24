# Cloud Database API Endpoints

This document describes the cloud database API endpoints available in the petal-app-manager.

## Overview

The cloud API provides direct access to the cloud database with the same interface as the local database proxy. All endpoints automatically include the organization_id from the local database configuration and use the machine_id for authentication.

## Base URL

All endpoints are prefixed with `/cloud/` when the application is running.

## Authentication

Authentication is handled automatically using the CloudDBProxy which manages access tokens internally.

## Endpoints

### 1. Scan Table

**POST** `/cloud/scan-table`

Retrieves all records from a specific table in the cloud database for the current organization.

#### Request Body
```json
{
    "table_name": "your_table_name",
    "filters": [
        {
            "filter_key_name": "column_name",
            "filter_key_value": "value_to_filter"
        }
    ]
}
```

#### Response
```json
{
    "records": [...],
    "count": 10
}
```

#### Example
```bash
curl -X POST "http://localhost:8000/cloud/scan-table" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "flight_records",
    "filters": [
      {
        "filter_key_name": "status",
        "filter_key_value": "completed"
      }
    ]
  }'
```

### 2. Get Item

**POST** `/cloud/get-item`

Retrieves a specific item from the cloud database by its key.

#### Request Body
```json
{
    "table_name": "your_table_name",
    "key_name": "primary_key_column",
    "key_value": "specific_key_value"
}
```

#### Response
```json
{
    "item": {
        "id": "123",
        "data": "...",
        "organization_id": "org_123"
    }
}
```

#### Example
```bash
curl -X POST "http://localhost:8000/cloud/get-item" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "flight_records",
    "key_name": "flight_id",
    "key_value": "flight_123"
  }'
```

### 3. Set Item

**POST** `/cloud/set-item`

Creates a new item or overwrites an existing item in the cloud database.

#### Request Body
```json
{
    "table_name": "your_table_name",
    "item_data": {
        "key": "value",
        "another_field": "another_value"
    }
}
```

#### Response
```json
{
    "success": true,
    "message": "Item created/updated successfully"
}
```

#### Example
```bash
curl -X POST "http://localhost:8000/cloud/set-item" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "flight_records",
    "item_data": {
      "flight_id": "flight_456",
      "pilot_name": "John Doe",
      "duration": 3600,
      "status": "completed"
    }
  }'
```

### 4. Update Item

**POST** `/cloud/update-item`

Updates specific fields of an existing item in the cloud database.

#### Request Body
```json
{
    "table_name": "your_table_name",
    "key_name": "primary_key_column",
    "key_value": "specific_key_value",
    "update_data": {
        "field_to_update": "new_value",
        "another_field": "another_new_value"
    }
}
```

#### Response
```json
{
    "success": true,
    "message": "Item updated successfully"
}
```

#### Example
```bash
curl -X POST "http://localhost:8000/cloud/update-item" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "flight_records",
    "key_name": "flight_id",
    "key_value": "flight_123",
    "update_data": {
      "status": "completed",
      "end_time": "2025-07-24T10:30:00Z"
    }
  }'
```

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200**: Success
- **400**: Bad Request (missing required parameters)
- **404**: Not Found (item doesn't exist)
- **500**: Internal Server Error (cloud service issues)

Error responses include:
```json
{
    "detail": "Error description",
    "headers": {
        "source": "endpoint_name"
    }
}
```

## Notes

1. The `organization_id` is automatically added to all requests based on the local database configuration
2. All requests are authenticated using the machine_id from the local database
3. The endpoints use the same interface as the LocalDBProxy for consistency
4. Filters in the scan-table endpoint are additive to the organization filter
5. The set-item endpoint will automatically add `organization_id` if not present in the item data

## Integration

These endpoints are automatically available when the petal-app-manager starts up, provided that:

1. The CloudDBProxy is properly configured with cloud endpoint and access token URLs
2. The LocalDBProxy is configured with valid organization_id and machine_id
3. The cloud database service is accessible and responding

## Swagger Documentation

When the application is running, you can access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

The endpoints will appear under the "cloud" tag in the documentation.
