import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';
import { DashboardConfig } from '../types';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface DashboardProps {
  data: DashboardConfig;
}

type TabType = 'marketStructure' | 'category' | 'segmentation' | 'segments' | 'reviewAnalysis';

export const Dashboard: React.FC<dashboardprops> = ({ data }) => {
  const [activeTab, setActiveTab] = useState<tabtype>('marketStructure');

  const tabs: { id: TabType; label: string }[] = [
    { id: 'marketStructure', label: 'Market Structure' },
    { id: 'category', label: 'Category' },
    { id: 'segmentation', label: 'Segmentation' },
    { id: 'segments', label: 'Segments' },
    { id: 'reviewAnalysis', label: 'Review Analysis' },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'marketStructure':
        return (
          <div classname="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div classname="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-slate-100">
              <h3 classname="text-lg font-medium text-slate-800 mb-6">Sales & Revenue Performance</h3>
              <div classname="h-[400px] w-full">
                <responsivecontainer width="100%" height="100%">
                  <linechart data="{data.tabs.marketStructure.lineChartData}" margin="{{" top:="" 5,="" right:="" 30,="" left:="" 20,="" bottom:="" 5="" }}="">
                    <cartesiangrid strokedasharray="3 3" vertical="{false}" stroke="#f1f5f9"/>
                    <xaxis datakey="date" axisline="{false}" tickline="{false}" tick="{{" fill:="" '#64748b',="" fontsize:="" 12="" }}="" dy="{10}"/>
                    <yaxis axisline="{false}" tickline="{false}" tick="{{" fill:="" '#64748b',="" fontsize:="" 12="" }}=""/>
                    <tooltip contentstyle="{{" backgroundcolor:="" '#fff',="" borderradius:="" '8px',="" border:="" '1px="" solid="" #e2e8f0'="" }}=""/>
                    <legend verticalalign="top" height="{36}" icontype="circle"/>
                    <line type="monotone" datakey="sales" stroke="#3b82f6" strokewidth="{3}" dot="{{" r:="" 4,="" fill:="" '#3b82f6',="" strokewidth:="" 2,="" stroke:="" '#fff'="" }}="" name="Sales (Units)"/>
                    <line type="monotone" datakey="revenue" stroke="#10b981" strokewidth="{3}" dot="{{" r:="" 4,="" fill:="" '#10b981',="" strokewidth:="" 2,="" stroke:="" '#fff'="" }}="" name="Revenue ($)"/>
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div classname="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
              <h3 classname="text-lg font-medium text-slate-800 mb-6">Traffic Distribution</h3>
              <div classname="h-[300px] w-full">
                <responsivecontainer width="100%" height="100%">
                  <piechart>
                    <pie data="{data.tabs.marketStructure.pieChartData}" cx="50%" cy="50%" innerradius="{60}" outerradius="{80}" paddingangle="{5}" datakey="value">
                      {data.tabs.marketStructure.pieChartData.map((entry, index) => (
                        <cell key="{`cell-${index}`}" fill="{entry.color}"/>
                      ))}
                    </Pie>
                    <tooltip/>
                    <legend layout="vertical" align="right" verticalalign="middle" icontype="circle"/>
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        );
      case 'category':
      case 'segments':
        const tableData = activeTab === 'category' ? data.tabs.category.tableData : data.tabs.segments.tableData;
        return (
          <div classname="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
            <div classname="p-6 border-b border-slate-100">
              <h3 classname="text-lg font-medium text-slate-800">{activeTab === 'category' ? 'Category Metrics' : 'Segment Metrics'}</h3>
            </div>
            <div classname="overflow-x-auto">
              <table classname="w-full text-left border-collapse">
                <thead>
                  <tr classname="bg-slate-50">
                    <th classname="px-6 py-4 text-sm font-semibold text-slate-600">Metric</th>
                    <th classname="px-6 py-4 text-sm font-semibold text-slate-600">Current</th>
                    <th classname="px-6 py-4 text-sm font-semibold text-slate-600">Previous</th>
                    <th classname="px-6 py-4 text-sm font-semibold text-slate-600">Change</th>
                  </tr>
                </thead>
                <tbody classname="divide-y divide-slate-100">
                  {tableData.map((row) => (
                    <tr key="{row.id}" classname="hover:bg-slate-50/50 transition-colors">
                      <td classname="px-6 py-4 text-sm font-medium text-slate-700">{row.metric}</td>
                      <td classname="px-6 py-4 text-sm text-slate-600">{row.current}</td>
                      <td classname="px-6 py-4 text-sm text-slate-600">{row.previous}</td>
                      <td classname="px-6 py-4 text-sm">
                        <div classname="{cn(&#34;flex" items-center="" gap-1="" font-medium",="" row.change=""> 0 ? "text-emerald-600" : row.change < 0 ? "text-rose-600" : "text-slate-400")}>
                          {row.change > 0 ? <trendingup classname="w-4 h-4"/> : row.change < 0 ? <trendingdown classname="w-4 h-4"/> : <minus classname="w-4 h-4"/>}
                          {Math.abs(row.change)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      case 'segmentation':
        return (
          <div classname="bg-white p-6 rounded-xl shadow-sm border border-slate-100 max-w-2xl mx-auto">
            <h3 classname="text-lg font-medium text-slate-800 mb-6">Segmentation Breakdown</h3>
            <div classname="h-[400px] w-full">
              <responsivecontainer width="100%" height="100%">
                <piechart>
                  <pie data="{data.tabs.segmentation.pieChartData}" cx="50%" cy="50%" innerradius="{80}" outerradius="{120}" paddingangle="{5}" datakey="value" label="">
                    {data.tabs.segmentation.pieChartData.map((entry, index) => (
                      <cell key="{`cell-${index}`}" fill="{entry.color}"/>
                    ))}
                  </Pie>
                  <tooltip/>
                  <legend verticalalign="bottom" height="{36}"/>
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        );
      case 'reviewAnalysis':
        return (
          <div classname="space-y-8">
            <div classname="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
              <h3 classname="text-lg font-medium text-slate-800 mb-6">Review Sentiment Trend</h3>
              <div classname="h-[300px] w-full">
                <responsivecontainer width="100%" height="100%">
                  <linechart data="{data.tabs.reviewAnalysis.lineChartData}">
                    <cartesiangrid strokedasharray="3 3" vertical="{false}" stroke="#f1f5f9"/>
                    <xaxis datakey="date" axisline="{false}" tickline="{false}"/>
                    <yaxis axisline="{false}" tickline="{false}"/>
                    <tooltip/>
                    <line type="monotone" datakey="sales" stroke="#f59e0b" strokewidth="{3}" name="Avg Rating"/>
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div classname="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
              <table classname="w-full text-left border-collapse">
                <tbody classname="divide-y divide-slate-100">
                  {data.tabs.reviewAnalysis.tableData.map((row) => (
                    <tr key="{row.id}">
                      <td classname="px-6 py-4 text-sm font-medium text-slate-700">{row.metric}</td>
                      <td classname="px-6 py-4 text-sm text-slate-600">{row.current}</td>
                      <td classname="px-6 py-4 text-sm text-slate-600">{row.previous}</td>
                      <td classname="px-6 py-4 text-sm font-medium text-emerald-600">{row.change}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
    }
  };

  return (
    <motion.div initial="{{" opacity:="" 0,="" y:="" 20="" }}="" animate="{{" opacity:="" 1,="" y:="" 0="" }}="" transition="{{" duration:="" 0.5="" }}="" classname="space-y-8">
      {/* Header & Description */}
      <div classname="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
        <div classname="flex items-center gap-3 mb-4">
          <div classname="p-2 bg-blue-50 rounded-lg">
            <info classname="w-5 h-5 text-blue-600"/>
          </div>
          <h2 classname="text-2xl font-semibold text-slate-900">{data.title}</h2>
          <span classname="px-3 py-1 bg-slate-100 text-slate-600 text-sm font-medium rounded-full">
            {data.market}
          </span>
        </div>
        <p classname="text-slate-600 leading-relaxed max-w-3xl">
          {data.description}
        </p>
      </div>

      {/* Drill-down Tabs */}
      <div classname="flex items-center gap-1 p-1 bg-slate-100 rounded-xl w-fit">
        {tabs.map((tab) => (
          <button key="{tab.id}" onclick="{()" ==""> setActiveTab(tab.id)}
            className={cn(
              "px-4 py-2 text-sm font-medium rounded-lg transition-all",
              activeTab === tab.id 
                ? "bg-white text-blue-600 shadow-sm" 
                : "text-slate-500 hover:text-slate-700 hover:bg-slate-50"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <animatepresence mode="wait">
        <motion.div key="{activeTab}" initial="{{" opacity:="" 0,="" y:="" 10="" }}="" animate="{{" opacity:="" 1,="" y:="" 0="" }}="" exit="{{" opacity:="" 0,="" y:="" -10="" }}="" transition="{{" duration:="" 0.2="" }}="">
          {renderTabContent()}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
};
