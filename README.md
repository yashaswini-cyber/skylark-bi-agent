# Skylark BI Agent

A conversational Business Intelligence agent built for the Skylark Drones Full Stack Developer Assignment.

The application connects live monday.com Deals and Work Order data to a deterministic analytics layer and a conversational interface, allowing business users to ask natural-language questions about pipeline, deals, billing, and operations.

## Live Application

**Application:** `ADD_DEPLOYED_FRONTEND_URL_HERE`

**Backend API:** https://skylark-bi-agent-backend-2c47.onrender.com

**API Documentation:** `ADD_DEPLOYED_BACKEND_URL_HERE/docs`

---

## Problem

Business data is often distributed across operational systems and requires manual filtering and interpretation before useful insights can be obtained.

The objective of this project is to provide a conversational interface over Skylark's monday.com data so that a business user can ask questions such as:

- How is the Mining pipeline doing?
- What is our current receivables?
- How many deals are currently open?
- What is the current work order status?
- Which sectors have the highest operational activity?

The focus of the implementation is not simply generating answers, but ensuring that business metrics are calculated from verified source data.

---

## Solution

The application follows a layered architecture:

```text
                         User
                           |
                           v
                  React Frontend
                           |
                       REST API
                           |
                           v
                    FastAPI Backend
                           |
              +------------+------------+
              |                         |
              v                         v
       Query Planner              monday.com
              |                         |
              |                         v
              |                  Data Normalizer
              |                         |
              |                         v
              |                 Analytics Engine
              |                         |
              +------------+------------+
                           |
                           v
                   Verified Results
                           |
                           v
                    Answer Generator
                           |
                           v
                    Business Response
