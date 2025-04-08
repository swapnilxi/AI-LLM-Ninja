"use client";
import { useState } from 'react';
import styles from './Tabs.module.css';
import Sidebar from './Sidebar';
import TurbofanPage from './tab-1/tab-1';
import Tab2 from './tab-2/MaintenanceTabs';
import ChatUI from './tab3/Chat';

const Tabs = () => {
  const [activeTab, setActiveTab] = useState('Chat');

  return (
    <div className={styles.container}>
      <Sidebar />
      <div className={styles.mainContent}>
        <div className={styles.tabContainer}>
          {['Tab 1', 'Maintenance Tab', 'Chat'].map((tab) => (
            <div
              key={tab}
              className={`${styles.tab} ${activeTab === tab ? styles.active : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </div>
          ))}
        </div>
        <div className={styles.content}>
          {activeTab === 'Tab 1' && <TurbofanPage />}
          {activeTab === 'Maintenance Tab' && <Tab2 />}
          {activeTab === 'Chat' && <ChatUI />}
        </div>
      </div>
    </div>
  );
};

export default Tabs;
