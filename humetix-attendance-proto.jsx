import { useState, useEffect, useRef } from "react";

const EMPLOYEES = [
  { id: 1, name: "이채현", dept: "영진팩" },
  { id: 2, name: "한성웅", dept: "영진팩" },
  { id: 3, name: "정민선", dept: "영진팩" },
  { id: 4, name: "김수빈", dept: "영진팩" },
  { id: 5, name: "김명인", dept: "영진팩" },
  { id: 6, name: "성민규", dept: "영진팩" },
  { id: 7, name: "윤청", dept: "영진팩" },
  { id: 8, name: "우아름", dept: "영진팩" },
  { id: 9, name: "이은비", dept: "영진팩" },
  { id: 10, name: "박윤수", dept: "영진팩" },
  { id: 11, name: "김수민", dept: "영진팩" },
  { id: 12, name: "김성태", dept: "영진팩" },
  { id: 13, name: "이혁연", dept: "영진팩" },
];

const SAMPLE_RECORDS = [
  { id: 1, empId: 1, date: "2026-02-12", clockIn: "08:00", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 2, empId: 2, date: "2026-02-12", clockIn: "08:30", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 3, empId: 3, date: "2026-02-12", clockIn: "08:30", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 4, empId: 4, date: "2026-02-12", clockIn: "08:30", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 5, empId: 5, date: "2026-02-12", clockIn: "08:00", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 6, empId: 6, date: "2026-02-12", clockIn: "08:00", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 7, empId: 7, date: "2026-02-12", clockIn: "08:30", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 8, empId: 8, date: "2026-02-12", clockIn: "08:30", clockOut: "21:00", overtime: 3, type: "normal" },
  { id: 9, empId: 9, date: "2026-02-12", clockIn: "08:30", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 10, empId: 10, date: "2026-02-12", clockIn: "08:30", clockOut: "19:00", overtime: 1.5, type: "normal" },
  { id: 11, empId: 11, date: "2026-02-12", clockIn: "19:00", clockOut: "08:30", overtime: 4.5, type: "night" },
  { id: 12, empId: 12, date: "2026-02-12", clockIn: "19:00", clockOut: "08:30", overtime: 4.5, type: "night" },
  { id: 13, empId: 13, date: "2026-02-12", clockIn: "19:00", clockOut: "08:30", overtime: 4.5, type: "night" },
];

const formatCurrency = (n) => n.toLocaleString("ko-KR") + "원";
const BASE_SALARY = 2200000;
const OT_RATE = 15000;

function generatePayslip(emp, records) {
  const totalOT = records.filter(r => r.empId === emp.id).reduce((s, r) => s + r.overtime, 0);
  const otPay = totalOT * OT_RATE;
  const gross = BASE_SALARY + otPay;
  const tax = Math.round(gross * 0.033);
  const insurance = Math.round(gross * 0.045 + gross * 0.035 + gross * 0.009 + gross * 0.008);
  const net = gross - tax - insurance;
  return { emp, totalOT, otPay, gross, tax, insurance, net, baseSalary: BASE_SALARY };
}

// Animated counter
function AnimNum({ value, prefix = "", suffix = "" }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    let start = 0;
    const end = value;
    const duration = 800;
    const startTime = Date.now();
    const tick = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(start + (end - start) * eased));
      if (progress < 1) ref.current = requestAnimationFrame(tick);
    };
    ref.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(ref.current);
  }, [value]);
  return <span>{prefix}{display.toLocaleString("ko-KR")}{suffix}</span>;
}

// Icons
const Icons = {
  dashboard: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
  ),
  clock: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
    </svg>
  ),
  pay: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
    </svg>
  ),
  user: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
    </svg>
  ),
  download: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  ),
  send: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
    </svg>
  ),
  check: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  ),
  sun: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="5"/></svg>
  ),
  moon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
  ),
  menu: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  ),
};

const STYLE = `
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;900&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg: #f8f7f4;
  --bg2: #ffffff;
  --bg3: #f0efec;
  --text: #1a1a1a;
  --text2: #6b6b6b;
  --accent: #e85d26;
  --accent2: #ff8c5a;
  --accent-bg: #fef3ee;
  --border: #e8e6e1;
  --success: #22a867;
  --success-bg: #edfbf3;
  --warning: #f59e0b;
  --night: #6366f1;
  --night-bg: #eef2ff;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-lg: 0 10px 25px rgba(0,0,0,0.08), 0 4px 10px rgba(0,0,0,0.04);
  --radius: 12px;
  --radius-sm: 8px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body, html, #root {
  font-family: 'Noto Sans KR', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(-12px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

@keyframes shimmer {
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
}

.app-wrap {
  display: flex;
  min-height: 100vh;
}

/* Sidebar */
.sidebar {
  width: 240px;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  z-index: 100;
  transition: transform 0.3s ease;
}

.sidebar-overlay {
  display: none;
}

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
  }
  .sidebar.open {
    transform: translateX(0);
  }
  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    z-index: 99;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s;
  }
  .sidebar-overlay.open {
    opacity: 1;
    pointer-events: auto;
  }
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: var(--accent);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 900;
  font-size: 16px;
}

.logo-text {
  font-weight: 700;
  font-size: 17px;
  letter-spacing: -0.3px;
}

.logo-sub {
  font-size: 11px;
  color: var(--text2);
  font-weight: 400;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--text2);
  transition: all 0.2s;
  margin-bottom: 2px;
}

.nav-item:hover {
  background: var(--bg3);
  color: var(--text);
}

.nav-item.active {
  background: var(--accent-bg);
  color: var(--accent);
  font-weight: 600;
}

.sidebar-footer {
  margin-top: auto;
  padding: 16px 8px 0;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--text2);
}

/* Main */
.main {
  flex: 1;
  margin-left: 240px;
  padding: 32px;
  max-width: 1200px;
}

@media (max-width: 768px) {
  .main { margin-left: 0; padding: 16px; padding-top: 70px; }
}

.mobile-header {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  z-index: 50;
  padding: 0 16px;
  align-items: center;
  gap: 12px;
}

@media (max-width: 768px) {
  .mobile-header { display: flex; }
}

.mobile-menu-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text);
  padding: 4px;
}

.page-title {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.5px;
  margin-bottom: 8px;
  animation: fadeUp 0.4s ease;
}

.page-desc {
  color: var(--text2);
  font-size: 14px;
  margin-bottom: 28px;
  animation: fadeUp 0.4s ease 0.05s both;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}

.stat-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  animation: fadeUp 0.5s ease both;
  transition: transform 0.2s, box-shadow 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.stat-label {
  font-size: 12px;
  color: var(--text2);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 800;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: -1px;
}

.stat-value.accent { color: var(--accent); }
.stat-value.success { color: var(--success); }
.stat-value.night { color: var(--night); }

.stat-sub {
  font-size: 12px;
  color: var(--text2);
  margin-top: 4px;
}

/* Table */
.table-wrap {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  animation: fadeUp 0.5s ease 0.15s both;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
  gap: 12px;
}

.table-title {
  font-weight: 700;
  font-size: 15px;
}

.table-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

thead { background: var(--bg3); }

th {
  padding: 10px 16px;
  text-align: left;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text2);
  white-space: nowrap;
}

td {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  white-space: nowrap;
}

tr:hover td {
  background: var(--bg3);
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
}

.badge-day {
  background: var(--accent-bg);
  color: var(--accent);
}

.badge-night {
  background: var(--night-bg);
  color: var(--night);
}

.badge-leave {
  background: #fef3c7;
  color: #b45309;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
  white-space: nowrap;
}

.btn-primary {
  background: var(--accent);
  color: white;
}

.btn-primary:hover {
  background: #d14e1a;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(232, 93, 38, 0.3);
}

.btn-outline {
  background: var(--bg2);
  color: var(--text);
  border: 1px solid var(--border);
}

.btn-outline:hover {
  background: var(--bg3);
  border-color: var(--text2);
}

.btn-success {
  background: var(--success);
  color: white;
}

.btn-success:hover {
  background: #1a9157;
}

.btn-sm {
  padding: 5px 10px;
  font-size: 12px;
}

/* Payslip */
.payslip {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  animation: fadeUp 0.5s ease both;
}

.payslip-header {
  background: linear-gradient(135deg, #1a1a1a, #333);
  color: white;
  padding: 28px;
  position: relative;
  overflow: hidden;
}

.payslip-header::after {
  content: '';
  position: absolute;
  top: -50%;
  right: -20%;
  width: 200px;
  height: 200px;
  background: var(--accent);
  border-radius: 50%;
  opacity: 0.1;
}

.payslip-company {
  font-size: 12px;
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 4px;
}

.payslip-title {
  font-size: 22px;
  font-weight: 800;
  margin-bottom: 12px;
}

.payslip-meta {
  display: flex;
  gap: 24px;
  font-size: 13px;
  opacity: 0.8;
}

.payslip-body {
  padding: 24px;
}

.payslip-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
}

.payslip-row:last-child {
  border-bottom: none;
}

.payslip-row.total {
  font-weight: 800;
  font-size: 18px;
  padding: 16px 0 8px;
  border-top: 2px solid var(--text);
  border-bottom: none;
  color: var(--accent);
}

.payslip-section {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text2);
  padding: 16px 0 8px;
}

.payslip-actions {
  display: flex;
  gap: 8px;
  padding: 0 24px 24px;
}

/* Employee input */
.input-page {
  max-width: 480px;
  margin: 0 auto;
}

.input-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
  animation: fadeUp 0.5s ease both;
}

.input-card h3 {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text2);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-input, .form-select {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-family: inherit;
  background: var(--bg);
  color: var(--text);
  transition: border-color 0.2s;
}

.form-input:focus, .form-select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(232, 93, 38, 0.1);
}

.time-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.quick-btns {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.quick-btn {
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--bg);
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.quick-btn:hover, .quick-btn.selected {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.success-msg {
  background: var(--success-bg);
  border: 1px solid #86efac;
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #166534;
  font-weight: 500;
  animation: fadeUp 0.3s ease;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  animation: fadeIn 0.2s;
  padding: 16px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-content {
  background: var(--bg2);
  border-radius: var(--radius);
  max-width: 520px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  animation: fadeUp 0.3s ease;
}

/* Send notification */
.notif-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: #1a1a1a;
  color: white;
  padding: 14px 20px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  animation: fadeUp 0.3s ease;
  z-index: 300;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Responsive table */
.table-scroll {
  overflow-x: auto;
}

.emp-name {
  font-weight: 600;
}

.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
}

/* Date filter */
.date-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.date-input {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
  background: var(--bg);
}

.tab-row {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  background: var(--bg3);
  padding: 4px;
  border-radius: var(--radius-sm);
  width: fit-content;
}

.tab-btn {
  padding: 7px 16px;
  border-radius: 6px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  background: transparent;
  color: var(--text2);
  transition: all 0.2s;
}

.tab-btn.active {
  background: var(--bg2);
  color: var(--text);
  box-shadow: var(--shadow);
}
`;

export default function HumetixAttendance() {
  const [page, setPage] = useState("dashboard");
  const [records] = useState(SAMPLE_RECORDS);
  const [showPayslip, setShowPayslip] = useState(null);
  const [toast, setToast] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [clockIn, setClockIn] = useState("08:30");
  const [clockOut, setClockOut] = useState("19:00");
  const [selectedEmp, setSelectedEmp] = useState(1);
  const [payTab, setPayTab] = useState("list");

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const totalEmployees = EMPLOYEES.length;
  const dayWorkers = records.filter(r => r.type === "normal").length;
  const nightWorkers = records.filter(r => r.type === "night").length;
  const totalOT = records.reduce((s, r) => s + r.overtime, 0);

  const navItems = [
    { id: "dashboard", icon: Icons.dashboard, label: "대시보드" },
    { id: "attendance", icon: Icons.clock, label: "근태 기록" },
    { id: "payslip", icon: Icons.pay, label: "급여명세서" },
    { id: "input", icon: Icons.user, label: "근무 입력" },
  ];

  return (
    <>
      <style>{STYLE}</style>
      <div className="app-wrap">
        {/* Mobile Header */}
        <div className="mobile-header">
          <button className="mobile-menu-btn" onClick={() => setSidebarOpen(true)}>
            {Icons.menu}
          </button>
          <span style={{ fontWeight: 700, fontSize: 15 }}>HUMETIX</span>
        </div>

        {/* Sidebar Overlay */}
        <div className={`sidebar-overlay ${sidebarOpen ? 'open' : ''}`} onClick={() => setSidebarOpen(false)} />

        {/* Sidebar */}
        <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
          <div className="logo">
            <div className="logo-icon">H</div>
            <div>
              <div className="logo-text">HUMETIX</div>
              <div className="logo-sub">근태관리 시스템</div>
            </div>
          </div>

          {navItems.map(item => (
            <div
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => { setPage(item.id); setSidebarOpen(false); }}
            >
              {item.icon}
              {item.label}
            </div>
          ))}

          <div className="sidebar-footer">
            <div style={{ fontWeight: 600, marginBottom: 2 }}>영진팩</div>
            <div>관리자 모드</div>
          </div>
        </div>

        {/* Main Content */}
        <div className="main">
          {/* Dashboard */}
          {page === "dashboard" && (
            <>
              <h1 className="page-title">대시보드</h1>
              <p className="page-desc">2026년 2월 12일 근무 현황 요약</p>

              <div className="stats-grid">
                <div className="stat-card" style={{ animationDelay: "0s" }}>
                  <div className="stat-label">총 근무인원</div>
                  <div className="stat-value"><AnimNum value={totalEmployees} suffix="명" /></div>
                  <div className="stat-sub">등록 직원 기준</div>
                </div>
                <div className="stat-card" style={{ animationDelay: "0.05s" }}>
                  <div className="stat-label">주간 근무</div>
                  <div className="stat-value accent"><AnimNum value={dayWorkers} suffix="명" /></div>
                  <div className="stat-sub">08:00 ~ 19:00</div>
                </div>
                <div className="stat-card" style={{ animationDelay: "0.1s" }}>
                  <div className="stat-label">야간 근무</div>
                  <div className="stat-value night"><AnimNum value={nightWorkers} suffix="명" /></div>
                  <div className="stat-sub">19:00 ~ 08:30</div>
                </div>
                <div className="stat-card" style={{ animationDelay: "0.15s" }}>
                  <div className="stat-label">총 잔업시간</div>
                  <div className="stat-value success"><AnimNum value={totalOT} suffix="h" /></div>
                  <div className="stat-sub">금일 누적</div>
                </div>
              </div>

              <div className="table-wrap">
                <div className="table-header">
                  <div className="table-title">오늘의 근무 현황</div>
                  <div className="table-actions">
                    <button className="btn btn-outline btn-sm" onClick={() => showToast("엑셀 다운로드 완료!")}>
                      {Icons.download} 엑셀
                    </button>
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>이름</th>
                        <th>출근</th>
                        <th>퇴근</th>
                        <th>잔업</th>
                        <th>구분</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.map((r, i) => {
                        const emp = EMPLOYEES.find(e => e.id === r.empId);
                        return (
                          <tr key={r.id} style={{ animation: `slideIn 0.3s ease ${i * 0.03}s both` }}>
                            <td className="emp-name">{emp?.name}</td>
                            <td className="mono">{r.clockIn}</td>
                            <td className="mono">{r.clockOut}</td>
                            <td className="mono">{r.overtime}h</td>
                            <td>
                              <span className={`badge ${r.type === "normal" ? "badge-day" : "badge-night"}`}>
                                {r.type === "normal" ? "☀ 주간" : "☽ 야간"}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* Attendance Records */}
          {page === "attendance" && (
            <>
              <h1 className="page-title">근태 기록</h1>
              <p className="page-desc">직원별 출퇴근 및 잔업 기록을 관리합니다</p>

              <div className="date-filter" style={{ marginBottom: 20 }}>
                <input type="date" className="date-input" defaultValue="2026-02-01" />
                <span style={{ color: "var(--text2)" }}>~</span>
                <input type="date" className="date-input" defaultValue="2026-02-28" />
                <button className="btn btn-primary btn-sm">조회</button>
              </div>

              <div className="table-wrap">
                <div className="table-header">
                  <div className="table-title">2026년 2월 근태 기록</div>
                  <div className="table-actions">
                    <button className="btn btn-outline btn-sm" onClick={() => showToast("엑셀 다운로드 완료!")}>
                      {Icons.download} 엑셀 다운로드
                    </button>
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>이름</th>
                        <th>날짜</th>
                        <th>출근</th>
                        <th>퇴근</th>
                        <th>잔업</th>
                        <th>구분</th>
                        <th>상태</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.map((r, i) => {
                        const emp = EMPLOYEES.find(e => e.id === r.empId);
                        return (
                          <tr key={r.id} style={{ animation: `slideIn 0.3s ease ${i * 0.03}s both` }}>
                            <td className="emp-name">{emp?.name}</td>
                            <td className="mono">{r.date}</td>
                            <td className="mono">{r.clockIn}</td>
                            <td className="mono">{r.clockOut}</td>
                            <td className="mono">{r.overtime}h</td>
                            <td>
                              <span className={`badge ${r.type === "normal" ? "badge-day" : "badge-night"}`}>
                                {r.type === "normal" ? "주간" : "야간"}
                              </span>
                            </td>
                            <td>
                              <span className="badge" style={{ background: "var(--success-bg)", color: "var(--success)" }}>
                                {Icons.check} 확인됨
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* Payslip */}
          {page === "payslip" && (
            <>
              <h1 className="page-title">급여명세서</h1>
              <p className="page-desc">직원별 급여명세서를 생성하고 전송할 수 있습니다</p>

              <div className="tab-row">
                <button className={`tab-btn ${payTab === "list" ? "active" : ""}`} onClick={() => setPayTab("list")}>직원 목록</button>
                <button className={`tab-btn ${payTab === "bulk" ? "active" : ""}`} onClick={() => setPayTab("bulk")}>일괄 전송</button>
              </div>

              {payTab === "list" && (
                <div className="table-wrap">
                  <div className="table-header">
                    <div className="table-title">2026년 2월 급여</div>
                    <div className="table-actions">
                      <button className="btn btn-outline btn-sm" onClick={() => showToast("전체 엑셀 다운로드 완료!")}>
                        {Icons.download} 전체 엑셀
                      </button>
                      <button className="btn btn-success btn-sm" onClick={() => showToast("✅ 13명에게 알림톡 발송 완료!")}>
                        {Icons.send} 일괄 전송
                      </button>
                    </div>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>이름</th>
                          <th>기본급</th>
                          <th>잔업시간</th>
                          <th>잔업수당</th>
                          <th>실수령액</th>
                          <th>액션</th>
                        </tr>
                      </thead>
                      <tbody>
                        {EMPLOYEES.map((emp, i) => {
                          const ps = generatePayslip(emp, records);
                          return (
                            <tr key={emp.id} style={{ animation: `slideIn 0.3s ease ${i * 0.03}s both` }}>
                              <td className="emp-name">{emp.name}</td>
                              <td className="mono">{formatCurrency(ps.baseSalary)}</td>
                              <td className="mono">{ps.totalOT}h</td>
                              <td className="mono">{formatCurrency(ps.otPay)}</td>
                              <td className="mono" style={{ fontWeight: 700, color: "var(--accent)" }}>{formatCurrency(ps.net)}</td>
                              <td>
                                <div style={{ display: "flex", gap: 4 }}>
                                  <button className="btn btn-outline btn-sm" onClick={() => setShowPayslip(emp)}>
                                    상세
                                  </button>
                                  <button className="btn btn-primary btn-sm" onClick={() => showToast(`✅ ${emp.name}님에게 전송 완료!`)}>
                                    {Icons.send}
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {payTab === "bulk" && (
                <div className="input-card" style={{ maxWidth: 600 }}>
                  <h3>급여명세서 일괄 전송</h3>
                  <div className="form-group">
                    <label className="form-label">전송 방법</label>
                    <select className="form-select">
                      <option>카카오 알림톡</option>
                      <option>SMS / LMS</option>
                      <option>이메일</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">대상 기간</label>
                    <input type="month" className="form-input" defaultValue="2026-02" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">대상 직원</label>
                    <div style={{ fontSize: 14, color: "var(--text2)", padding: "8px 0" }}>
                      전체 {EMPLOYEES.length}명 선택됨
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn btn-primary" onClick={() => showToast(`✅ ${EMPLOYEES.length}명에게 급여명세서 전송 완료!`)}>
                      {Icons.send} 일괄 전송
                    </button>
                    <button className="btn btn-outline" onClick={() => showToast("PDF 파일 다운로드 완료!")}>
                      {Icons.download} 전체 PDF 다운로드
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Employee Input */}
          {page === "input" && (
            <>
              <h1 className="page-title">근무 입력</h1>
              <p className="page-desc">오늘의 출퇴근 및 잔업 시간을 입력하세요</p>

              <div className="input-page">
                {submitted ? (
                  <div>
                    <div className="success-msg" style={{ marginBottom: 16 }}>
                      {Icons.check} 근무 기록이 정상적으로 등록되었습니다!
                    </div>
                    <div className="input-card">
                      <div style={{ textAlign: "center", padding: "20px 0" }}>
                        <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
                        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
                          {EMPLOYEES.find(e => e.id === selectedEmp)?.name}
                        </div>
                        <div style={{ color: "var(--text2)", fontSize: 14, marginBottom: 16 }}>
                          {clockIn} 출근 → {clockOut} 퇴근
                        </div>
                        <button className="btn btn-outline" onClick={() => setSubmitted(false)}>
                          다시 입력하기
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="input-card">
                    <h3>📋 근무 시간 입력</h3>

                    <div className="form-group">
                      <label className="form-label">이름</label>
                      <select className="form-select" value={selectedEmp} onChange={e => setSelectedEmp(Number(e.target.value))}>
                        {EMPLOYEES.map(emp => (
                          <option key={emp.id} value={emp.id}>{emp.name}</option>
                        ))}
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">날짜</label>
                      <input type="date" className="form-input" defaultValue="2026-02-19" />
                    </div>

                    <div className="time-row">
                      <div className="form-group">
                        <label className="form-label">출근 시간</label>
                        <input type="time" className="form-input" value={clockIn} onChange={e => setClockIn(e.target.value)} />
                        <div className="quick-btns">
                          <button className={`quick-btn ${clockIn === "08:00" ? "selected" : ""}`} onClick={() => setClockIn("08:00")}>08:00</button>
                          <button className={`quick-btn ${clockIn === "08:30" ? "selected" : ""}`} onClick={() => setClockIn("08:30")}>08:30</button>
                          <button className={`quick-btn ${clockIn === "19:00" ? "selected" : ""}`} onClick={() => setClockIn("19:00")}>19:00</button>
                        </div>
                      </div>
                      <div className="form-group">
                        <label className="form-label">퇴근 시간</label>
                        <input type="time" className="form-input" value={clockOut} onChange={e => setClockOut(e.target.value)} />
                        <div className="quick-btns">
                          <button className={`quick-btn ${clockOut === "19:00" ? "selected" : ""}`} onClick={() => setClockOut("19:00")}>19:00</button>
                          <button className={`quick-btn ${clockOut === "21:00" ? "selected" : ""}`} onClick={() => setClockOut("21:00")}>21:00</button>
                          <button className={`quick-btn ${clockOut === "08:30" ? "selected" : ""}`} onClick={() => setClockOut("08:30")}>08:30</button>
                        </div>
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label">근무 유형</label>
                      <select className="form-select">
                        <option>주간 근무</option>
                        <option>야간 근무</option>
                        <option>연차</option>
                        <option>반차</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">비고</label>
                      <input type="text" className="form-input" placeholder="특이사항 입력 (선택)" />
                    </div>

                    <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center", padding: "12px" }} onClick={() => setSubmitted(true)}>
                      근무 기록 등록
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Payslip Modal */}
        {showPayslip && (() => {
          const ps = generatePayslip(showPayslip, records);
          return (
            <div className="modal-overlay" onClick={() => setShowPayslip(null)}>
              <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="payslip">
                  <div className="payslip-header">
                    <div className="payslip-company">HUMETIX Co., Ltd.</div>
                    <div className="payslip-title">급여명세서</div>
                    <div className="payslip-meta">
                      <span>👤 {ps.emp.name}</span>
                      <span>🏢 {ps.emp.dept}</span>
                      <span>📅 2026년 2월</span>
                    </div>
                  </div>
                  <div className="payslip-body">
                    <div className="payslip-section">지급 내역</div>
                    <div className="payslip-row">
                      <span>기본급</span>
                      <span className="mono">{formatCurrency(ps.baseSalary)}</span>
                    </div>
                    <div className="payslip-row">
                      <span>잔업수당 ({ps.totalOT}시간 × {formatCurrency(OT_RATE)})</span>
                      <span className="mono">{formatCurrency(ps.otPay)}</span>
                    </div>
                    <div className="payslip-row" style={{ fontWeight: 600 }}>
                      <span>총 지급액</span>
                      <span className="mono">{formatCurrency(ps.gross)}</span>
                    </div>

                    <div className="payslip-section">공제 내역</div>
                    <div className="payslip-row">
                      <span>소득세 (3.3%)</span>
                      <span className="mono" style={{ color: "#dc2626" }}>-{formatCurrency(ps.tax)}</span>
                    </div>
                    <div className="payslip-row">
                      <span>4대보험</span>
                      <span className="mono" style={{ color: "#dc2626" }}>-{formatCurrency(ps.insurance)}</span>
                    </div>

                    <div className="payslip-row total">
                      <span>실수령액</span>
                      <span>{formatCurrency(ps.net)}</span>
                    </div>
                  </div>
                  <div className="payslip-actions">
                    <button className="btn btn-primary" onClick={() => { showToast("PDF 다운로드 완료!"); setShowPayslip(null); }}>
                      {Icons.download} PDF 다운로드
                    </button>
                    <button className="btn btn-success" onClick={() => { showToast(`✅ ${ps.emp.name}님에게 알림톡 전송 완료!`); setShowPayslip(null); }}>
                      {Icons.send} 알림톡 전송
                    </button>
                    <button className="btn btn-outline" onClick={() => setShowPayslip(null)}>
                      닫기
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Toast */}
        {toast && <div className="notif-toast">{toast}</div>}
      </div>
    </>
  );
}
