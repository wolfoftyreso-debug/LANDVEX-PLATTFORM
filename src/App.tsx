import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Companies from "./pages/Companies";
import CompanyProfile from "./pages/CompanyProfile";
import CompanyRegister from "./pages/CompanyRegister";
import RfqNew from "./pages/RfqNew";
import RfqBrowse from "./pages/RfqBrowse";
import RfqDetail from "./pages/RfqDetail";
import OrderDetail from "./pages/OrderDetail";
import Dashboard from "./pages/Dashboard";
import Messages from "./pages/Messages";
import CompanyEdit from "./pages/CompanyEdit";
import AdminBackOffice from "./pages/AdminBackOffice";
import Auth from "./pages/Auth";
import ResetPassword from "./pages/ResetPassword";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/companies" element={<Companies />} />
          <Route path="/company/register" element={<CompanyRegister />} />
          <Route path="/company/edit" element={<CompanyEdit />} />
          <Route path="/company/:slug" element={<CompanyProfile />} />
          <Route path="/rfq/new" element={<RfqNew />} />
          <Route path="/rfq/:id" element={<RfqDetail />} />
          <Route path="/rfqs" element={<RfqBrowse />} />
          <Route path="/order/:id" element={<OrderDetail />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/messages" element={<Messages />} />
          <Route path="/admin" element={<AdminBackOffice />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
