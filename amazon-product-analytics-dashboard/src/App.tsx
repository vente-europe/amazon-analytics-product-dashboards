import React, { useState, useEffect } from 'react';
import { Dashboard } from './components/Dashboard';
import { DashboardConfig, DashboardListResponse } from './types';
import { LayoutDashboard, Plus, Upload, Loader2, AlertCircle, ChevronRight, Package } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export default function App() {
  const [dashboards, setDashboards] = useState<{ id: string; title: string; market: string; group: 'detailed' | 'top-line' }[]>([]);
  const [activeId, setActiveId] = useState<string |="" null="">(null);
  const [activeData, setActiveData] = useState<dashboardconfig |="" null="">(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string |="" null="">(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadJson, setUploadJson] = useState('');

  const isAdmin = new URLSearchParams(window.location.search).get('admin') === 'true';

  // Fetch list of dashboards
  useEffect(() => {
    fetchDashboards();
  }, []);

  const fetchDashboards = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/dashboards');
      const data: DashboardListResponse = await res.json();
      setDashboards(data.dashboards);
      if (data.dashboards.length > 0 && !activeId) {
        setActiveId(data.dashboards[0].id);
      }
    } catch (err) {
      setError('Failed to load dashboards list');
    } finally {
      setLoading(false);
    }
  };

  const detailedDashboards = dashboards.filter(d => d.group === 'detailed');
  const topLineDashboards = dashboards.filter(d => d.group === 'top-line');

  // Fetch specific dashboard data when activeId changes
  useEffect(() => {
    if (activeId) {
      fetchDashboardData(activeId);
    }
  }, [activeId]);

  const fetchDashboardData = async (id: string) => {
    try {
      setLoading(true);
      const res = await fetch(`/api/dashboards/${id}`);
      const data: DashboardConfig = await res.json();
      setActiveData(data);
    } catch (err) {
      setError(`Failed to load data for ${id}`);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    try {
      const data = JSON.parse(uploadJson);
      const res = await fetch('/api/dashboards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        setShowUploadModal(false);
        setUploadJson('');
        fetchDashboards();
        setActiveId(data.id);
      } else {
        alert('Failed to save dashboard');
      }
    } catch (err) {
      alert('Invalid JSON format');
    }
  };

  if (loading && !activeData) {
    return (
      <div classname="min-h-screen bg-slate-50 flex items-center justify-center">
        <div classname="flex flex-col items-center gap-4">
          <loader2 classname="w-8 h-8 text-blue-600 animate-spin"/>
          <p classname="text-slate-500 font-medium">Loading Analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div classname="min-h-screen bg-slate-50 flex">
      {/* Sidebar Navigation */}
      <aside classname="w-72 bg-white border-r border-slate-200 flex flex-col sticky top-0 h-screen">
        <div classname="p-6 border-b border-slate-100">
          <div classname="flex items-center gap-3 text-blue-600 mb-2">
            <layoutdashboard classname="w-6 h-6"/>
            <h1 classname="text-xl font-bold tracking-tight text-slate-900">Amazon Analytics</h1>
          </div>
          <p classname="text-xs text-slate-400 font-medium uppercase tracking-wider">Product Dashboards</p>
        </div>

        <nav classname="flex-1 overflow-y-auto p-4 space-y-6">
          {topLineDashboards.length > 0 && (
            <div classname="space-y-2">
              <h3 classname="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest">Top Line</h3>
              <div classname="space-y-1">
                {topLineDashboards.map(db => (
                  <button key="{db.id}" onclick="{()" ==""> setActiveId(db.id)}
                    className={`w-full flex items-center justify-between p-3 rounded-lg text-sm font-medium transition-all group ${
                      activeId === db.id
                        ? 'bg-blue-50 text-blue-700 shadow-sm'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                  >
                    <div classname="flex items-center gap-3">
                      <package classname="{`w-4" h-4="" ${activeid="==" db.id="" ?="" 'text-blue-600'="" :="" 'text-slate-400="" group-hover:text-slate-600'}`}=""/>
                      <span classname="truncate max-w-[140px]">{db.title}</span>
                    </div>
                    <chevronright classname="{`w-4" h-4="" transition-transform="" ${activeid="==" db.id="" ?="" 'translate-x-0="" opacity-100'="" :="" '-translate-x-2="" opacity-0'}`}=""/>
                  </button>
                ))}
              </div>
            </div>
          )}

          {detailedDashboards.length > 0 && (
            <div classname="space-y-2">
              <h3 classname="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest">Dashboards Detailed</h3>
              <div classname="space-y-1">
                {detailedDashboards.map(db => (
                  <button key="{db.id}" onclick="{()" ==""> setActiveId(db.id)}
                    className={`w-full flex items-center justify-between p-3 rounded-lg text-sm font-medium transition-all group ${
                      activeId === db.id
                        ? 'bg-blue-50 text-blue-700 shadow-sm'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                  >
                    <div classname="flex items-center gap-3">
                      <package classname="{`w-4" h-4="" ${activeid="==" db.id="" ?="" 'text-blue-600'="" :="" 'text-slate-400="" group-hover:text-slate-600'}`}=""/>
                      <span classname="truncate max-w-[140px]">{db.title}</span>
                    </div>
                    <chevronright classname="{`w-4" h-4="" transition-transform="" ${activeid="==" db.id="" ?="" 'translate-x-0="" opacity-100'="" :="" '-translate-x-2="" opacity-0'}`}=""/>
                  </button>
                ))}
              </div>
            </div>
          )}
        </nav>

        {isAdmin && (
          <div classname="p-4 border-t border-slate-100 bg-slate-50/50">
            <button onclick="{()" ==""> setShowUploadModal(true)}
              className="w-full flex items-center justify-center gap-2 p-3 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all shadow-sm"
            >
              <plus classname="w-4 h-4"/>
              Add New Product
            </button>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <main classname="flex-1 p-8 max-w-7xl mx-auto w-full">
        <animatepresence mode="wait">
          {error ? (
            <motion.div key="error" initial="{{" opacity:="" 0,="" y:="" 10="" }}="" animate="{{" opacity:="" 1,="" y:="" 0="" }}="" exit="{{" opacity:="" 0,="" y:="" -10="" }}="" classname="bg-rose-50 border border-rose-100 p-6 rounded-xl flex items-center gap-4 text-rose-700">
              <alertcircle classname="w-6 h-6"/>
              <p classname="font-medium">{error}</p>
            </motion.div>
          ) : activeData ? (
            <motion.div key="{activeId}" initial="{{" opacity:="" 0,="" x:="" 20="" }}="" animate="{{" opacity:="" 1,="" x:="" 0="" }}="" exit="{{" opacity:="" 0,="" x:="" -20="" }}="" transition="{{" duration:="" 0.3="" }}="">
              <dashboard data="{activeData}"/>
            </motion.div>
          ) : (
            <div classname="flex flex-col items-center justify-center h-full text-slate-400">
              <layoutdashboard classname="w-16 h-16 mb-4 opacity-20"/>
              <p>Select a product to view analytics</p>
            </div>
          )}
        </AnimatePresence>
      </main>

      {/* Upload Modal */}
      {showUploadModal && (
        <div classname="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <motion.div initial="{{" opacity:="" 0,="" scale:="" 0.95="" }}="" animate="{{" opacity:="" 1,="" scale:="" 1="" }}="" classname="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
            <div classname="p-6 border-b border-slate-100 flex items-center justify-between">
              <div classname="flex items-center gap-3">
                <div classname="p-2 bg-blue-50 rounded-lg">
                  <upload classname="w-5 h-5 text-blue-600"/>
                </div>
                <h2 classname="text-xl font-bold text-slate-900">Import Product Data</h2>
              </div>
              <button onclick="{()" ==""> setShowUploadModal(false)} className="text-slate-400 hover:text-slate-600">
                <plus classname="w-6 h-6 rotate-45"/>
              </button>
            </div>
            <div classname="p-6 space-y-4">
              <p classname="text-sm text-slate-500">
                Paste your dashboard JSON configuration below. This will create a new local file in the backend.
              </p>
              <textarea value="{uploadJson}" onchange="{(e)" ==""> setUploadJson(e.target.value)}
                placeholder='{ "id": "new-product", "title": "Product Name", ... }'
                className="w-full h-64 p-4 font-mono text-xs bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
              />
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUpload}
                  className="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors shadow-md shadow-blue-200"
                >
                  Save Dashboard
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
