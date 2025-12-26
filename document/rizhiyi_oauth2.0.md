# **日志易平台提供基于 OAuth 2.0 授权服务**

## **1、需求描述**

日志易平台对外提供基于 OAuth 2.0 规范的授权接口

OAuth 2.0
规范：[[https://datatracker.ietf.org/doc/html/rfc6749]](https://datatracker.ietf.org/doc/html/rfc6749)

## **2、如果需要，业界其他厂商的解决方案调研**

参考以下厂商的流程和接口实现:

Datadog:
[[https://docs.datadoghq.com/developers/authorization/oauth2_in_datadog/]](https://docs.datadoghq.com/developers/authorization/oauth2_in_datadog/)

Github:
[[https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps]](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)

微信:
[[https://developers.weixin.qq.com/doc/offiaccount/OA_Web_Apps/Wechat_webpage_authorization.html]](https://developers.weixin.qq.com/doc/offiaccount/OA_Web_Apps/Wechat_webpage_authorization.html)

AWS:
[[https://docs.aws.amazon.com/cognito/latest/developerguide/federation-endpoints.html]](https://docs.aws.amazon.com/cognito/latest/developerguide/federation-endpoints.html)

## **3、方案设计**

### 3.1 具体方案

#### 3.1.1 角色定义

**Resource Owner**

资源所有者，所拥有资源受权限保护，可以授权给第三方其拥有资源的访问权限。在日志易平台中即看作拥有日志易平台中资源的用户

**Resource Server**

资源服务器，提供受权限保护的资源，第三方可以使用 access_tokens 来获取指定资源。在日志易平台中即可看作日志易平台中提供资源的服务

**Authorization Server**

授权服务器，提供资源所有者授权流程，并且在授权后提供可以用于访问受权限保护资源的 access_tokens。在日志易平台中即可看作日志易平台中提供授权的服务

**Client**

"第三方应用"，在授权后代表资源所有者从资源服务器读取其受权限保护的资源

#### 3.1.2 流程简图

OAuth 2.0 中基本流程图如下所示：

```mermaid
sequenceDiagram
    participant C as Client
    participant RO as Resource Owner
    participant AS as Authorization Server
    participant RS as Resource Server

    C->>RO: (A) Authorization Request
    RO-->>C: (B) Authorization Grant

    C->>AS: (C) Authorization Grant
    AS-->>C: (D) Access Token

    C->>RS: (E) Access Token
    RS-->>C: (F) Protected Resource
```

#### 3.1.3 流程步骤简述

Oauth 2.0 规范支持 4 种流程:

-   Authorization Code
-   Implicit
-   Resource Owner Password Credentials
-   Client Credentials

其中复杂度，安全性和适用度最高的是 **Authorization Code** 流程,
其流程也被称为 Web Application Flow, 其流程如下:

1.  第三方应用引导用户进入OAuth2.0服务提供方授权服务提供的授权页面(日志易平台提供的 OAuth2.0 授权页面)  
  * OAuth2.0服务提供方(日志易平台)检测用户是否已经为登录/认证状态，未登录用户提供登陆页面进行用户认证，已登陆用户进行下一步
  * 当确认用户认证状态后，提供用户授权页面，告知用户授权相关信息，用户点击授权按钮进行授权确认
  * 跳转至第三方应用提供的redirect url 并以 querystring 的形式返回授权码Code
2.  第三方应用使用步骤一中获取的用户授权码 Code 请求日志易平台提供的授权服务 Token 相关接口获取访问资源的 access token
3.  第三方应用使用步骤二中获取的 access token 来请求日志易平台提供的资源服务的指定接口来访问用户资源

```mermaid
sequenceDiagram
    participant RO as Resource Owner
    participant UA as User-Agent (Browser)
    participant C as Client (Application)
    participant AS as Authorization Server

    RO-->>UA: (B) User initiates interaction 
    Note right of RO: Resource Owner (User)

    C->>UA: (A) Client Identifier & Redirection URI
    UA->>AS: (A) Client Identifier & Redirection URI

    UA->>AS: (B) User authenticates
    AS-->>UA: (C) Authorization Code

    UA->>C: (C) Authorization Code

    C->>AS: (D) Authorization Code & Redirection URI
    AS-->>C: (E) Access Token (w/ Optional Refresh Token)
```

### 3.3 服务接口设计

#### 3.3.1 用户授权页面

此 URL 路径提供 OAuth2.0
服务授权页面，包含登陆和授权确认等用户交互行为，当日志易认证用户确认授权行为后实际调用
API 服务器提供的 OAuth2.0 授权接口获取授权码 Code 并返回给第三方应用。

`GET /oauth2/authorize/`

请求参数

| 参数名称 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| `response_type` | `enum<string>` | 是 | 返回类型，请填写 **code** |
| `client_id` | `string` | 是 | 第三方应用的唯一标识，由日志易平台签发 |
| `redirect_url` | `string` | 是 | 授权后重定向的回调链接地址， 请使用 urlEncode 对链接进行处理 |
| `state` | `string` | 否 | 一串随机字符组合，如果提供则在跳转 redirect_url 携带; 用于防止 CSRF 攻击 |

请求示例

`GET
https://日志易平台地址/oauth2/authorize/?response_type=code&client_id=APP_CLIENT_ID&redirect_url=https://YOUR_APP/redirect_url&state=STATE`

成功示例

授权成功后重定向跳转到第三方应用提供的 redirect url 并且携带授权码 code
和 state

`GET https://YOUR_APP/redirect_url?code=AUTHORIZATION_CODE&state=STATE`

| 参数名称 | 类型 | 说明 |
|---|---|---|
| `code` | `string` | 授权码，有效期为 10 分钟，并且只能使用 1 次来请求 access_token |
| `state` | `string` | 如果请求中提供 state 参数则原样返回该参数 |
失败示例

授权失败应该给第三方应用返回失败原因

`GET https://YOUR_APP/redirect_url?error=REASON`

#### 3.3.2 用户授权接口

当认证用户授权确认后, 请求此接口获取授权码
Code。(**此接口为内部实现接口，调用需要认证，第三方应用在 OAuth
流程中无需调用此接口**)

```
GET /api/v3/oauth2/authorize/
# 在请求 headers 中使用 Authorization 项来使用 Basic/Bearer
方式来认证用户
Authorization: Basic base64(username:password)
```

请求参数

| 参数名称 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| `response_type` | `enum<string>` | 是 | 返回类型，请填写 **code** |
| `client_id` | `string` | 是 | 第三方应用的唯一标识，由日志易平台签发 |
| `redirect_url` | `string` | 是 | 授权后重定向的回调链接地址 |
| `state` | `string` | 否 | 一串随机字符组合，如果提供则在跳转 redirect_url 携带; 用于防止 CSRF 攻击 |
请求示例

`GET
https://日志易平台地址/api/v3/oauth2/authorize/?response_type=code&client_id=APP_CLIENT_ID&redirect_url=https://YOUR_APP/redirect_url&state=STATE`

成功示例

接口调用成功后 (result 为 true) 返回 location 字段表面跳转地址:

**location 中的 code 有效期为 10 分钟且只有使用一次**

```
{
"location":
"https://www.baidu.com?code=Oflar1EoHcJTuHvzQJfoyw&state=STATE",
"result": true,
"traceid": "e83cb15e3cfe4e5fa78842bdfeb2ed50"
}
```

失败示例

接口调用失败后 (result 为 false) 会以 error 字段返回失败相关信息

```
{
"error": {},
"result": false,
"traceid": "e83cb15e3cfe4e5fa78842bdfeb2ed50"
}
```

#### 3.3.3 用户授权完成后获取 Token 接口

`POST /api/v3/oauth2/token/`

请求参数

| 参数名称 | 类型 | 是否必填 | 说明 |
|---|---|---|---|
| `client_id` | `string` | 是 | 第三方应用的唯一标识，由日志易平台签发 |
| `client_secret` | `string` | 是 | 第三方应用的secret, 由日志易平台签发 |
| `grant_type` | `enum<string>` | 是 | 授权类型，请填写 authorization_code |
| `code` | `string` | 是 | 在用户授权中获取的授权码 code |
| `redirect_url` | `string` | 是 | 必须和授权步骤中提供的 redirect_url 一致 |
请求示例

```
POST https://日志易平台地址/api/v3/oauth2/token/

grant_type=authorization_code
client_id=APP_CLIENT_ID
client_secret=APP_CLIENT_SECRET
code=AUTHORIZATION_CODE
redirect_url=https://YOUR_APP/redirect_url
```

成功示例

成功后返回的数据如下

```
{
  "token": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJAeW90dGFieXRlL2FwaSIsImlhdCI6MTc2NTUyNzQ1NSwiZXhwIjoxNzY1NTMxMDU1LCJqdGkiOiJlN2VmZDJkMS1jY2ZhLTQ4ZmUtYWI4Yi1lZTFiNjIzZDQ1OTUiLCJhcGlfdmVyc2lvbiI6InYzIiwic2NvcGUiOiJvYXV0aDIiLCJ1c2VyX2lkIjoxfQ.Mv_aMWyuWQ5GoWuTtZHtLvYdUbCCXT_FloipBR7QkFI",
    "token_type": "Bearer",
    "expire_in": 3600,
    "scope": "oauth2"
  },
  "result": true,
  "traceid": "9ecedf1085f0455b8b3bad4996883e17"
}
```

| 字段 | 数据类型 | 说明 |
|---|---|---|
| `token.access_token` | `string` | 可以获取指定资源的 access_token |
| `token.token_type` | `"Bearer"` | 指明 token 类型为 Bearer token |
| `token.expire_in` | `number` | access_token 过期时间，默认为 1 小时 |
| `token.scope` | `string` | 授权范围 |
| `result` | `boolean` | 请求结果状态 |
| `traceid` | `string` | 请求追踪ID |

#### 3.3.4 使用 access_token 获取用户相关信息

Get /api/v3/oauth2/userinfo/

请求示例

```
GET https://日志易平台地址/api/v3/oauth2/userinfo/
# 在请求 headers 中使用 Authorization 项来使用 access_token
Authorization: Bearer access_token
```

成功示例

成功后返回的数据如下

```
{
  "user": {
    "id": 1,
    "name": "admin",
    "email": "admin@rizhiyi.com"
  },
  "result": true,
  "traceid": "e83cb15e3cfe4e5fa78842bdfeb2ed50"
}
```

| 字段 | 数据类型 | 说明 |
|---|---|---|
| `user.id` | `number` | 用户ID |
| `user.name` | `string` | 用户名 |
| `user.email` | `string` | 用户邮箱 |
| `result` | `boolean` | 请求结果状态 |
| `traceid` | `string` | 请求追踪ID |

#### 3.3.5 错误处理

在整个 OAuth2.0 流程中可能出现以下错误类型：

* InvalidRequestException             
* InvalidClientException              
* InvalidGrantException               
* UnauthorizedClientException         
* UnsupportedResponseTypeException    
* UnsupportedGrantTypeException      

#### **3.4 数据库设计**

Authorization Code 表, 为资源所有者授权码的抽象

**rizhiyi_system.oauth_authorization_code**

| 列名 | 数据类型 | 非空 | 说明 |
|---|---|---|---|
| `id` | `bigint` | ✅ | 自增主键 |
| `code` | `varchar(255)` | ✅ | 授权码内容 |
| `expires_at` | `datetime` | ✅ | 授权码过期时间 |
| `user_id` | `bigint` | ✅ | 资源所有者标识 |
| `client_id` | `varchar(255)` | ✅ | 第三方应用标识 |
| `redirect_url` | `text` | ✅ | 第三方应用跳转地址 |
**建表语句**

**MySQL**

```sql
CREATE TABLE IF NOT EXISTS `oauth_authorization_code` (
`id` bigint(20) NOT NULL AUTO_INCREMENT,
`code` varchar(255) NOT NULL,
`expires_at` datetime NOT NULL,
`user_id` bigint(20) NOT NULL,
`client_id` varchar(255) NOT NULL,
`redirect_url` text,
PRIMARY KEY (`id`),
UNIQUE KEY `oauth_authorization_code_UN` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
```

**达梦**

```sql
CREATE TABLE IF NOT EXISTS rizhiyi_system.oauth_authorization_code (
id bigint NOT NULL IDENTITY(1, 1),
code varchar(255) NOT NULL,
expires_at timestamp NOT NULL,
user_id bigint NOT NULL,
client_id varchar(255) NOT NULL,
redirect_url text,
PRIMARY KEY (id),
CONSTRAINT oauth_authorization_code_UN UNIQUE (code)
);
```

**Postgresql**

```sql
CREATE TABLE IF NOT EXISTS rizhiyi_system.oauth_authorization_code (
id bigserial PRIMARY KEY,
code varchar(255) NOT NULL,
expires_at timestamptz NOT NULL,
user_id bigint NOT NULL,
client_id varchar(255) NOT NULL,
redirect_url text,
CONSTRAINT oauth_authorization_code_UN UNIQUE (code)
);
```