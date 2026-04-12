import { createBrowserRouter, Navigate } from "react-router-dom";

import { BetaLayout } from "../apps/beta/BetaLayout";
import { BetaChatPage } from "../apps/beta/pages/BetaChatPage";
import { BetaHomePage } from "../apps/beta/pages/BetaHomePage";
import { BetaResultPage } from "../apps/beta/pages/BetaResultPage";
import { AdminLayout } from "../apps/admin/AdminLayout";
import { AdminHomePage } from "../apps/admin/pages/AdminHomePage";
import { AdminSessionDetailPage } from "../apps/admin/pages/AdminSessionDetailPage";
import { AdminSessionsPage } from "../apps/admin/pages/AdminSessionsPage";

export const appRouter = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/beta" replace />,
  },
  {
    path: "/beta",
    element: <BetaLayout />,
    children: [
      {
        index: true,
        element: <BetaHomePage />,
      },
      {
        path: "chat",
        element: <BetaChatPage />,
      },
      {
        path: "result/:sessionId",
        element: <BetaResultPage />,
      },
    ],
  },
  {
    path: "/admin",
    element: <AdminLayout />,
    children: [
      {
        index: true,
        element: <AdminHomePage />,
      },
      {
        path: "sessions",
        element: <AdminSessionsPage />,
      },
      {
        path: "sessions/:sessionId",
        element: <AdminSessionDetailPage />,
      },
    ],
  },
]);
