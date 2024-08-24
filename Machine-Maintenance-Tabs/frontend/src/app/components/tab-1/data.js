// data.js
export const columns = [
  { uid: "name", name: "Name", sortable: true },
  { uid: "predictedEngineLife", name: "Predicted Engine Life", sortable: true },
  { uid: "status", name: "Status", sortable: false },
];

export const files = [
  { id: 1, turboEngine: "turboEngine1", name: "TK1345", predictedEngineLife: 45, status: "healthy", date: "2024-01-15" },
  { id: 2, turboEngine: "turboEngine1", name: "TK1398", predictedEngineLife: 10, status: "repair", date: "2024-03-20" },
  { id: 3, turboEngine: "turboEngine2", name: "TK1445", predictedEngineLife: 25, status: "caution", date: "2024-05-25" },
  // Add more data as needed
];

export const statusOptions = [
  { uid: "healthy", name: "healthy" },
  { uid: "repair", name: "repair" },
  { uid: "caution", name: "caution" },
];

export const timelineOptions = [
  { month: "January", year: 2024 },
  { month: "February", year: 2024 },
  { month: "March", year: 2024 },
  // Add more months and years as needed
];
