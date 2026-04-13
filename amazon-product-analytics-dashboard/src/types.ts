export interface LineChartPoint {
  date: string;
  sales: number;
  revenue: number;
  units: number;
}

export interface PieChartPoint {
  name: string;
  value: number;
  color: string;
}

export interface TableRow {
  id: string;
  metric: string;
  current: number;
  previous: number;
  change: number;
}

export interface DashboardConfig {
  id: string;
  title: string;
  market: string;
  group: 'detailed' | 'top-line';
  description: string;
  tabs: {
    marketStructure: {
      lineChartData: LineChartPoint[];
      pieChartData: PieChartPoint[];
    };
    category: {
      tableData: TableRow[];
    };
    segmentation: {
      pieChartData: PieChartPoint[];
    };
    segments: {
      tableData: TableRow[];
    };
    reviewAnalysis: {
      lineChartData: LineChartPoint[];
      tableData: TableRow[];
    };
  };
}

export interface DashboardListResponse {
  dashboards: { id: string; title: string; market: string; group: 'detailed' | 'top-line' }[];
}
