import React, { useState, useEffect, useCallback } from 'react';
// import './styles/styles.css'; // Imported in main.jsx

import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import BinManagement from './components/BinManagement';
import TruckManagement from './components/TruckManagement';
import RouteManagement from './components/RouteManagement';
import UserManagement from './components/UserManagement';
import Settings from './components/settings';
import UserForm from './components/UserForm';
import TruckForm from './components/TruckForm';
import RouteForm from './components/RouteForm';
import TruckAssignCollectorForm from './components/TruckAssignCollectorForm';
import BinForm from './components/BinForm';
import MaintenanceRequestForm from './components/MaintenanceRequestForm';
import TrackTruckModal from './components/TrackTruckModal';
import SettingsForm from './components/SettingsForm';

function App({ onLogout }) {
  const [activeMenu, setActiveMenu] = useState('dashboard');
  const [activeTab, setActiveTab] = useState('tab1');
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);
  const [modalState, setModalState] = useState({ open: false, type: null, data: null });
  const [notificationsVisible, setNotificationsVisible] = useState(false);
  const [notifications, setNotifications] = useState([
    { id: 1, type: 'warning', message: 'Bin #245 is 90% full', time: '10 min ago' },
    { id: 2, type: 'error', message: 'Truck #12 requires maintenance', time: '1 hour ago' }
  ]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);


  const updateMedia = useCallback(() => {
    const newIsMobile = window.innerWidth < 768;
    setIsMobile(newIsMobile);
    setSidebarOpen(!newIsMobile);
  }, []);


  useEffect(() => {
    window.addEventListener('resize', updateMedia);
    return () => window.removeEventListener('resize', updateMedia);
  }, [updateMedia]);

  useEffect(() => {
    updateMedia();
  }, [updateMedia]);


  const toggleSidebar = () => {
    setSidebarOpen(prev => !prev);
  };

  const toggleNotifications = () => {
    setNotificationsVisible(prev => !prev);
  };

  const handleMenuChange = (menuItem) => {
    setActiveMenu(menuItem);
    setActiveTab('tab1');
    if (isMobile && sidebarOpen) {
      setSidebarOpen(false);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
  };


// Handle button actions
const handleButtonAction = (action, data = {}) => {
  switch (action) {
    case 'add':
    case 'edit':
    case 'delete':
    case 'assign':
    case 'track':
    case 'complete':
    case 'add-maintenance':
    case 'edit-maintenance':
    case 'edit-profile': // <-- This is the action from settings.jsx
      setModalState({ open: true, type: action, data: data });
      break;
    case 'refresh':
      console.log('Refreshing data for', activeMenu);
      setRefreshKey(oldKey => oldKey + 1);
      break;
    case 'export':
      handleExport();
      break;
    case 'dismiss-notification':
      dismissNotification(data);
      break;
    case 'clear-notifications':
      setNotifications([]);
      break;
    default:
      console.log('Unknown action:', action);
  }
};

  // Handle data export
  const handleExport = () => {
    alert(`Exporting data from ${activeMenu}${activeTab ? ' - ' + activeTab : ''}`);
  };

  // Dismiss a single notification
  const dismissNotification = (notificationId) => {
    setNotifications(prev => prev.filter(notification => notification.id !== notificationId));
  };

  // Close modal
  const closeModal = () => {
    setModalState({ open: false, type: null, data: null });
    setIsDeleting(false);
  };

  // Save modal data
  const saveModalData = (formData) => {
    console.log('Saving data:', formData, 'for', activeMenu);
    closeModal();
    handleButtonAction('refresh');
  };

  // Logout handler
  const handleLogout = () => {
    if (onLogout) onLogout();
  };


// Updated renderModal function
const renderModal = () => {
  if (!modalState.open) return null;

  // Simplified entity name logic
  let currentEntityName = 'Item';
  if (activeMenu === 'bin-management') currentEntityName = 'Bin';
  else if (activeMenu === 'truck-management') currentEntityName = 'Truck';
  else if (activeMenu === 'route-management') currentEntityName = 'Route';
  else if (activeMenu === 'user-management') {
    currentEntityName = (modalState.data && modalState.data.type) ? modalState.data.type : 'User';
  }

  // Use modal type for title
  const title =
      modalState.type === 'add' ? `Add New ${currentEntityName}`
    : modalState.type === 'edit' ? `Edit ${currentEntityName}`
    : modalState.type === 'delete' ? `Delete ${currentEntityName}`
    : modalState.type === 'assign' ? `Assign ${currentEntityName}`
    : modalState.type === 'track' ? `Track ${currentEntityName}`
    : modalState.type === 'complete' ? `Complete ${currentEntityName}`
    : modalState.type === 'add-maintenance' ? `New Maintenance Request`
    : modalState.type === 'edit-maintenance' ? `Edit Maintenance Request`
    : modalState.type === 'edit-profile' ? `Edit Profile` // <-- NEW TITLE
    : 'Confirm Action';

  const handleDelete = async () => {
    if (modalState.data && modalState.data.deleteCallback) {
      setIsDeleting(true);
      try {
        await modalState.data.deleteCallback();
        closeModal();
        handleButtonAction('refresh');
      } catch (error) {
        console.error("Delete failed:", error);
      } finally {
        setIsDeleting(false);
      }
    } else {
      console.warn("No deleteCallback provided for modal.");
      closeModal();
    }
  };

  // Define all form states
  const isUserAdd = activeMenu === 'user-management' && modalState.type === 'add';
  const isUserEdit = activeMenu === 'user-management' && modalState.type === 'edit';
  const isTruckAdd = activeMenu === 'truck-management' && modalState.type === 'add';
  const isTruckEdit = activeMenu === 'truck-management' && modalState.type === 'edit';
  const isTruckAssign = activeMenu === 'truck-management' && modalState.type === 'assign';
  const isTruckTrack = activeMenu === 'truck-management' && modalState.type === 'track';
  const isBinAdd = activeMenu === 'bin-management' && modalState.type === 'add';
  const isBinEdit = activeMenu === 'bin-management' && modalState.type === 'edit';
  const isRouteAdd = activeMenu === 'route-management' && modalState.type === 'add';
  const isRouteEdit = activeMenu === 'route-management' && modalState.type === 'edit';
  const isMaintenanceAdd = modalState.type === 'add-maintenance';
  const isMaintenanceEdit = modalState.type === 'edit-maintenance';
  const isProfileEdit = modalState.type === 'edit-profile'; // <-- 3. NEW PROFILE EDIT STATE

  // Check if any *real* form is active (including the map view)
  const isFormActive = isUserAdd || isUserEdit || isTruckAdd || isTruckEdit || isTruckAssign || isBinAdd || isBinEdit || isRouteAdd || isRouteEdit || isMaintenanceAdd || isMaintenanceEdit || isProfileEdit;

  return (
    <div className="app__modal-overlay" onClick={closeModal} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="app__modal" onClick={(e) => e.stopPropagation()}>
        <div className="app__modal-header">
          <h2 id="modal-title">{title}</h2>
          <button className="app__modal-close" onClick={closeModal} type="button" aria-label="Close modal">
            ×
          </button>
        </div>
        <div className="app__modal-content">
          {modalState.type === 'delete' ? (
            <div className="app__modal-delete-confirm">
              <p>Are you sure you want to delete this {currentEntityName.toLowerCase()}?</p>
              {modalState.data && (modalState.data.name || modalState.data.binId || modalState.data.registrationNumber) && <p><strong>Item: {modalState.data.name || modalState.data.binId || modalState.data.registrationNumber}</strong></p>}
              <p>This action cannot be undone.</p>
            </div>
          ) : (
            <div className="app__modal-form">

              {isUserAdd && (
                <UserForm
                  role={modalState.data.type === 'Collector' ? 'ROLE_COLLECTOR' :
                       (modalState.data.type === 'Bin User' ? 'ROLE_BIN_OWNER' : 'ROLE_ADMIN')}
                  onCancel={closeModal}
                  onSave={saveModalData}
                  token={localStorage.getItem('token')}
                />
              )}
              {isUserEdit && (
                <UserForm
                  existingUser={modalState.data}
                  role={modalState.data.role}
                  onCancel={closeModal}
                  onSave={saveModalData}
                  token={localStorage.getItem('token')}
                />
              )}

              {isTruckAdd && (
                <TruckForm
                  onCancel={closeModal}
                  onSave={saveModalData}
                  token={localStorage.getItem('token')}
                />
              )}

              {isTruckEdit && (
                <TruckForm
                  existingTruck={modalState.data}
                  onCancel={closeModal}
                  onSave={saveModalData}
                  token={localStorage.getItem('token')}
                />
              )}

              {isTruckAssign && (
                <TruckAssignCollectorForm
                  truck={modalState.data.truck}
                  collectors={modalState.data.collectors}
                  onCancel={closeModal}
                  onSave={saveModalData}
                  token={localStorage.getItem('token')}
                />
              )}

              {isTruckTrack && (
                <TrackTruckModal
                  truckData={{
                    id: modalState.data.id,
                    registrationNumber: modalState.data.registrationNumber,
                  }}
                  onCancel={closeModal}
                  onSave={saveModalData}
                />
              )}


              {isRouteAdd && (
                <RouteForm
                  onCancel={closeModal}
                  onSave={saveModalData}
                  token={localStorage.getItem('token')}
                />
              )}

              {isRouteEdit && (
                <RouteForm
                  existingRoute={modalState.data}
                  onCancel={closeModal}
                  onSave={saveModalData}
                  token={localStorage.getItem('token')}
                />
              )}

              {isBinAdd && (
                 <BinForm
                    onCancel={closeModal}
                    onSave={saveModalData}
                    token={localStorage.getItem('token')}
                 />
              )}

              {isBinEdit && (
                 <BinForm
                    existingBin={modalState.data}
                    onCancel={closeModal}
                    onSave={saveModalData}
                    token={localStorage.getItem('token')}
                 />
              )}

              {isMaintenanceAdd && (
                <MaintenanceRequestForm
                    bins={modalState.data.bins}
                    onCancel={closeModal}
                    onSave={saveModalData}
                    token={localStorage.getItem('token')}
                />
              )}
              {isMaintenanceEdit && (
                <MaintenanceRequestForm
                    existingRequest={modalState.data}
                    bins={[]} // We don't need bins list for edit
                    onCancel={closeModal}
                    onSave={saveModalData}
                    token={localStorage.getItem('token')}
                />
              )}

              {/* --- 4. RENDER SETTINGS FORM --- */}
              {isProfileEdit && (
                <SettingsForm
                    userProfile={modalState.data.user} // Pass the fetched profile data
                    onCancel={closeModal}
                    onSave={saveModalData} // Save handler will trigger refresh
                    token={localStorage.getItem('token')}
                />
              )}
              {/* --- END RENDER SETTINGS FORM --- */}


              {/* Placeholder for all other forms */}
              {!isFormActive && (
                <>
                  <p>Form fields for '{modalState.type}' on a {currentEntityName.toLowerCase()} would go here.</p>
                  {modalState.data && (
                    <p>Item ID: {modalState.data.id || modalState.data.binId}</p>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {modalState.type === 'delete' ? (
            <div className="app__modal-footer">
              <button className="btn btn--secondary" onClick={closeModal} type="button" disabled={isDeleting}>
                Cancel
              </button>
              <button
                  className="btn btn--danger"
                  onClick={handleDelete}
                  type="button"
                  disabled={isDeleting}
                >
                  {isDeleting ? "Deleting..." : "Delete"}
                </button>
            </div>
        ) : !isFormActive ? (
            <div className="app__modal-footer">
              <button className="btn btn--secondary" onClick={closeModal} type="button">
                Cancel
              </button>
              <button
                  className="btn btn--primary"
                  onClick={() =>
                    saveModalData({
                      // ...
                    })
                  }
                  type="button"
                >
                  Save
                </button>
            </div>
        ) : (modalState.type === 'track' ? <div className="app__modal-footer"><button className="btn btn--secondary" onClick={closeModal} type="button">Close</button></div> : null) /* Show close button only for Track */ }
      </div>
    </div>
  );
};

  // Get entity name
  const getEntityName = () => {
    if (modalState.type === 'add-maintenance' || modalState.type === 'edit-maintenance') {
      return "Maintenance Request";
    }
    switch (activeMenu) {
      case 'bin-management': return 'Bin';
      case 'truck-management': return 'Truck';
      case 'route-management': return 'Route';
      case 'user-management':
        if (modalState.data && modalState.data.type) {
          return modalState.data.type;
        }
        return 'User';
      default: return 'Item';
    }
  };

  // Get tabs for current menu
  const getTabsForMenu = (menuItem) => {
    switch (menuItem) {
      case 'dashboard':
        return [
          { id: 'tab1', label: 'Overview' },
          { id: 'tab2', label: 'Statistics' },
          { id: 'tab3', label: 'Alerts' }
        ];
      case 'bin-management':
        return [
          { id: 'tab1', label: 'All Bins' },
          { id: 'tab2', label: 'Active Bins' },
          { id: 'tab3', label: 'Maintenance' },
          { id: 'tab4', label: 'Bin Map' }
        ];
      case 'truck-management':
        return [
          { id: 'tab1', label: 'Fleet' },
          { id: 'tab2', label: 'On Route' }
        ];
      case 'route-management':
        return [
          { id: 'tab1', label: 'Routes' },
          { id: 'tab2', label: 'Assignment' },
          { id: 'tab3', label: 'Map' }
        ];
      case 'user-management':
        return [
          { id: 'tab1', label: 'Collectors' },
          { id: 'tab2', label: 'Bin Users' },
          { id: 'tab3', label: 'Admins' }
        ];
      default:
        return [];
    }
  };

  // Render tab headers
  const renderTabHeaders = () => {
    const tabs = getTabsForMenu(activeMenu);
    if (!tabs || tabs.length === 0) return null;
    return (
      <div className="app__tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`app__tab-button ${activeTab === tab.id ? 'app__tab-button--active' : ''}`}
            onClick={(e) => {
              e.preventDefault();
              handleTabChange(tab.id);
            }}
            type="button"
          >
            {tab.label}
          </button>
        ))}
        <div className="app__tab-actions">
          <button className="app__action-button" onClick={() => handleButtonAction('refresh')} title="Refresh" type="button">
            ↻
          </button>
          {/* Hide Add button on Dash, User, and Route mgmt */}
          {activeMenu !== 'dashboard' && activeMenu !== 'user-management' && (
            <button className="app__action-button" onClick={() => handleButtonAction('add')} title={`Add ${getEntityName()}`} type="button">
              +
            </button>
          )}
        </div>
      </div>
    );
  };

  // Render notifications
  // Render notifications panel
    const renderNotifications = () => (
      <div className={`app__notifications ${notificationsVisible ? 'app__notifications--visible' : ''}`}>
        <div className="app__notifications-header">
          <h3>Notifications</h3>
          <button
              className="app__notifications-clear"
              onClick={() => handleButtonAction('clear-notifications')}
              disabled={notifications.length === 0}
          >
              Clear All
          </button>
        </div>

        <div className="app__notifications-list">
          {notifications.length === 0 ? (
             <div className="app__notifications-empty">No new notifications</div>
          ) : (
             notifications.map(notif => (
               <div key={notif.id} className={`app__notification app__notification--${notif.type === 'error' ? 'error' : notif.type === 'warning' ? 'warning' : 'info'}`}>
                 <div className="app__notification-content">
                   <p className="app__notification-message">{notif.message || notif.title}</p>
                   <span className="app__notification-time">
                      {notif.time || (notif.createdAt ? new Date(notif.createdAt).toLocaleTimeString() : 'Just now')}
                   </span>
                 </div>
                 <button
                   className="app__notification-dismiss"
                   onClick={() => handleButtonAction('dismiss-notification', notif.id)}
                   title="Dismiss"
                 >
                   ×
                 </button>
               </div>
             ))
          )}
        </div>
      </div>
    );

  const loggedInUser = {
    fullName: 'Admin User',
    email: 'admin@example.com',
    role: 'Administrator',
    memberSince: '2025-01-15',
  };

  // Render content
  const renderContent = () => {
    const key = `${activeMenu}-${refreshKey}`;
    // Pass onLogout to Dashboard and Settings
    const commonProps = { activeTab, onAction: handleButtonAction, isMobile, refreshKey: key, onLogout: handleLogout };

    switch (activeMenu) {
      case 'dashboard':
        return <Dashboard {...commonProps} notifications={notifications} />;
      case 'bin-management':
        return <BinManagement {...commonProps} />;
      case 'truck-management':
        return <TruckManagement {...commonProps} />;
      case 'route-management':
        return <RouteManagement {...commonProps} />;
      case 'user-management':
        return <UserManagement {...commonProps} />;
      case 'settings':
        return <Settings {...commonProps} user={loggedInUser} />;
      default:
        return <Dashboard {...commonProps} notifications={notifications} />;
    }
  };

  return (
    <div className="app">
      <Sidebar
        activeMenu={activeMenu}
        onMenuChange={handleMenuChange}
        sidebarOpen={sidebarOpen}
      />
      <div className={`app__main-content ${sidebarOpen ? 'app__main-content--sidebar-open' : ''}`}>
        <Header
          onToggleSidebar={toggleSidebar}
          onToggleNotifications={toggleNotifications}
          notificationCount={notifications.length}
          user={{ name: 'Admin User' }}
          onLogout={handleLogout}
        />
        <main className="app__content">
          {renderTabHeaders()}
          {renderContent()}
        </main>
      </div>
      {renderNotifications()}
      {renderModal()}
    </div>
  );
}

export default App;

