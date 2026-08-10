# Backend Architecture Proposal

## 1. Architectural Pattern
I propose using a layered architecture organized by business domain.

This approach fits the company because the system contains multiple business responsibilities and separate user interfaces, including the public website and the backoffice. The backend should keep API routes, business logic, and data access separated so that each responsibility can be changed without affecting the entire application.
The current project already includes a public website and a backoffice interface, with business areas such as product catalog management, product details, cart, and checkout. As these areas grow, separating their responsibilities in the backend will help prevent business logic from becoming mixed across the application.
The main layers would be:

- API layer: receives HTTP requests and returns responses through FastAPI endpoints.
- Service layer: contains the business logic and coordinates operations.
- Data access layer: handles communication with the database or other data sources.
- Models and schemas layer: defines the internal data models and the request and response structures.

The project should also be separated by business domains. For example, product-related functionality should be grouped separately from other domains instead of placing all backend logic in the same files.

This structure is appropriate for the project because it keeps the backend understandable as the application grows, reduces duplicated logic, and makes it easier for different developers or AI agents to work on separate areas of the system.

## 2. Backend Folder Structure
The backend should be organized so that each folder has a clear responsibility. A possible structure would be:

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── routers/
│   │   │   ├── products.py
│   │   │   ├── cart.py
│   │   │   └── orders.py
│   │   └── dependencies.py
│   ├── services/
│   │   ├── product_service.py
│   │   ├── cart_service.py
│   │   └── order_service.py
│   ├── models/
│   │   ├── product.py
│   │   ├── cart.py
│   │   └── order.py
│   ├── schemas/
│   │   ├── product.py
│   │   ├── cart.py
│   │   └── order.py
│   ├── repositories/
│   │   ├── product_repository.py
│   │   ├── cart_repository.py
│   │   └── order_repository.py
│   └── core/
│       └── config.py
└── tests/

## 3. FastAPI Routes Organization
The FastAPI routes should be grouped by business domain instead of placing every endpoint in one file.

Each router would manage one main area of the application. For example:

- `products.py` would manage product-related endpoints.
- `cart.py` would manage cart-related endpoints.
- `orders.py` would manage order-related endpoints.

Possible routes could include:

- `GET /products` to return the available products.
- `GET /products/{product_id}` to return one product.
- `POST /products` to create a product for authorized backoffice users.
- `PUT /products/{product_id}` to update product information.
- `GET /orders` to return orders.
- `POST /orders` to create a new order.
- `GET /cart` to return the current shopping cart.
- `POST /cart/items` to add a product to the cart.

Each router should be registered in `main.py` using FastAPI's router system.

The route files should mainly be responsible for receiving requests, validating input, calling the appropriate service, and returning the response. Business logic should remain in the service layer instead of being written directly inside the endpoint functions.

This organization makes the API easier to understand and maintain because developers can quickly identify which file is responsible for each business area.

## 4. FastAPI Research
FastAPI applications can be organized into multiple files instead of keeping the entire API in one file. According to the official FastAPI documentation, larger applications commonly use a main application file together with separate router modules.

FastAPI provides `APIRouter` to group related endpoints. For example, product routes can be placed in a products router while user routes can be placed in a users router. These routers can then be included in the main FastAPI application.

This convention influenced the proposed structure of this project. The backend would keep `main.py` small and use separate router files for each business domain. Models, schemas, services, and configuration would also be placed in separate modules so that each part of the application has a clear responsibility.

FastAPI documentation also explains that application configuration such as database URLs, credentials, and other settings can be stored in environment variables instead of being written directly into the source code. This is useful because development, testing, and production environments may require different configuration values.

Source:
- FastAPI Official Documentation — Bigger Applications: Multiple Files
- FastAPI Official Documentation — Settings and Environment Variables

## 5. Frontend and Backend Integration
The frontend and backend should remain separate systems that communicate through HTTP API requests.

The frontend would send requests to the FastAPI backend using endpoints such as `/products`, `/users`, and `/orders`. The backend would process the request, apply the required business logic, access the data if necessary, and return a response to the frontend.

The frontend should not hardcode the backend URL directly in the source code. Instead, the API base URL should be stored in an environment variable so that different environments can use different backend addresses.

For example:

- Development may use a local backend URL.
- Testing may use a test server.
- Production may use the deployed backend URL.

Because the frontend and backend may run on different origins, the backend may also need CORS configuration. CORS should only allow the frontend origins that are expected to communicate with the API.

Keeping the frontend and backend separated makes it easier to deploy and maintain them independently while still allowing them to communicate through a clearly defined API.

## 6. Risks and Points of Attention
If the proposed structure is not followed, the project could become harder to maintain as new features are added.

One risk is that business logic could be placed directly inside route files. This would make the routes large and difficult to test, reuse, or modify. Keeping the business logic in the service layer helps avoid this problem.

A second risk is mixing unrelated business domains in the same files. For example, placing product, user, and order logic together would make the code harder to understand and could create unnecessary dependencies between different parts of the application.

Another point of attention is configuration management. Sensitive values such as database credentials or API keys should not be hardcoded in the source code. They should be stored securely using environment variables.

The team should also keep the API contracts consistent between the frontend and backend. Changes to request or response structures should be coordinated so that frontend features do not break unexpectedly.

Finally, the CORS configuration should be restrictive and only allow trusted frontend origins. Allowing every origin without a clear reason could create unnecessary security risks.

## 7. References
FastAPI Official Documentation — Bigger Applications: Multiple Files  
  https://fastapi.tiangolo.com/tutorial/bigger-applications/

FastAPI Official Documentation — Settings and Environment Variables  
  https://fastapi.tiangolo.com/advanced/settings/