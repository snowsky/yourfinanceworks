import React, { useState, useEffect } from 'react';
import { logger } from './src/utils/logger';
import { View, StyleSheet, Alert, Text } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import './src/i18n'; // Initialize i18n
import LoginScreen from './src/screens/LoginScreen';
import SignupScreen from './src/screens/SignupScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import InvoicesScreen from './src/screens/InvoicesScreen';
import NewInvoiceScreen from './src/screens/NewInvoiceScreen';
import EditInvoiceScreen from './src/screens/EditInvoiceScreen';
import ClientsScreen from './src/screens/ClientsScreen';
import NewClientScreen from './src/screens/NewClientScreen';
import EditClientScreen from './src/screens/EditClientScreen';
import PaymentsScreen from './src/screens/PaymentsScreen';
import ExpensesScreen from './src/screens/ExpensesScreen';
import NewExpenseScreen from './src/screens/NewExpenseScreen';
import EditExpenseScreen from './src/screens/EditExpenseScreen';
import StatementsScreen from './src/screens/StatementsScreen';
import AnalyticsScreen from './src/screens/AnalyticsScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import UsersScreen from './src/screens/UsersScreen';
import ForgotPasswordScreen from './src/screens/ForgotPasswordScreen';
import ResetPasswordScreen from './src/screens/ResetPasswordScreen';
import apiService, { User, Client, Invoice, CreateInvoiceData, UpdateInvoiceData, InvoiceItemCreate, InvoiceItemUpdate, Expense, BankStatement, set401ErrorHandler } from './src/services/api';

type Screen = 'login' | 'signup' | 'forgotPassword' | 'resetPassword' | 'dashboard' | 'invoices' | 'newInvoice' | 'editInvoice' | 'clients' | 'newClient' | 'editClient' | 'payments' | 'expenses' | 'newExpense' | 'editExpense' | 'statements' | 'analytics' | 'settings' | 'users';

const App: React.FC = () => {
  const [currentScreen, setCurrentScreen] = useState<Screen>('login');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<number | null>(null);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);
  const [resetToken, setResetToken] = useState<string>('');
  const [user, setUser] = useState<User | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Set up 401 error handler to redirect to login
    set401ErrorHandler(() => {
      logger.info('401 error detected, redirecting to login');
      setIsAuthenticated(false);
      setUser(null);
      setCurrentScreen('login');
    });

    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const isAuth = await apiService.isAuthenticated();
      if (isAuth) {
        const currentUser = await apiService.getStoredUser();
        setUser(currentUser);
        setIsAuthenticated(true);
        setCurrentScreen('dashboard');
        await loadData();
      }
    } catch (error: any) {
      console.error('Auth check failed:', error);
      // If it's a 401 error, the handler will already redirect to login
      // Otherwise, stay on login screen
    } finally {
      setLoading(false);
    }
  };

  const loadData = async () => {
    try {
      const [clientsData, invoicesData] = await Promise.all([
        apiService.getClients(),
        apiService.getInvoices(),
      ]);

      // Fetch detailed invoice data with items
      const detailedInvoices = await Promise.all(
        invoicesData.map(inv => apiService.getInvoice(inv.id))
      );

      setClients(clientsData);
      setInvoices(detailedInvoices);
    } catch (error: any) {
      console.error('Failed to load data:', error);
      // If it's a 401 error, the handler will redirect to login
      // Otherwise, show error but don't crash the app
    }
  };

  const handleLogin = async (email: string, password: string) => {
    try {
      const response = await apiService.login({ email, password });
      setUser(response.user);
      setIsAuthenticated(true);
      setCurrentScreen('dashboard');
      await loadData();
    } catch (error: any) {
      throw new Error(error.message || 'Login failed');
    }
  };

  const handleNavigateToSignup = () => {
    setCurrentScreen('signup');
  };

  const handleNavigateToForgotPassword = () => {
    setCurrentScreen('forgotPassword');
  };

  const handleNavigateToResetPassword = (token: string) => {
    setResetToken(token);
    setCurrentScreen('resetPassword');
  };

  const handleNavigateToInvoices = () => {
    setCurrentScreen('invoices');
  };

  const handleNavigateToClients = () => {
    setCurrentScreen('clients');
  };

  const handleNavigateToPayments = () => {
    setCurrentScreen('payments');
  };

  const handleNavigateToExpenses = () => {
    setCurrentScreen('expenses');
  };

  const handleNavigateToNewExpense = () => {
    setCurrentScreen('newExpense');
  };

  const handleNavigateToEditExpense = (expense: Expense) => {
    setSelectedExpense(expense);
    setCurrentScreen('editExpense');
  };

  const handleNavigateToStatements = () => {
    setCurrentScreen('statements');
  };

  const handleNavigateToAnalytics = () => {
    setCurrentScreen('analytics');
  };

  const handleNavigateToSettings = () => {
    setCurrentScreen('settings');
  };

  const handleNavigateToNewInvoice = () => {
    setCurrentScreen('newInvoice');
  };

  const handleNavigateToNewClient = () => {
    setCurrentScreen('newClient');
  };

  const handleNavigateToEditClient = (client: Client) => {
    setSelectedClient(client);
    setCurrentScreen('editClient');
  };

  const handleNavigateToUsers = () => {
    setCurrentScreen('users');
  };


  const handleNavigateToEditInvoice = (invoiceId: number) => {
    setSelectedInvoice(invoiceId);
    setCurrentScreen('editInvoice');
  };

  const handleNavigateBack = () => {
    setCurrentScreen('dashboard');
  };

  const handleNavigateBackFromInvoice = () => {
    setCurrentScreen('invoices');
  };

  const handleNavigateBackFromEditInvoice = () => {
    setSelectedInvoice(null);
    setCurrentScreen('invoices');
  };

  const handleNavigateBackFromNewClient = () => {
    setCurrentScreen('clients');
  };

  const handleNavigateBackFromEditClient = () => {
    setSelectedClient(null);
    setCurrentScreen('clients');
  };

  const handleClientAdded = (newClient: Client) => {
    setClients(prev => [newClient, ...prev]);
  };

  const handleClientUpdated = (updatedClient: Client) => {
    setClients(prev => prev.map(client => 
      client.id === updatedClient.id ? updatedClient : client
    ));
  };

  const handleClientDeleted = (clientId: number) => {
    setClients(prev => (prev || []).filter(client => client.id !== clientId));
  };

  const handleNavigateToLogin = () => {
    setCurrentScreen('login');
  };

  const handleSignOut = async () => {
    try {
      await apiService.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setIsAuthenticated(false);
      setCurrentScreen('login');
      setSelectedInvoice(null);
      setSelectedClient(null);
      setResetToken('');
      setUser(null);
      setClients([]);
      setInvoices([]);
    }
  };

  const handleSignup = async (formData: {
    first_name: string;
    last_name: string;
    email: string;
    password: string;
    organization_name: string;
  }) => {
    try {
      const response = await apiService.signup(formData);
      setUser(response.user);
      setIsAuthenticated(true);
      setCurrentScreen('dashboard');
      await loadData();
    } catch (error: any) {
      throw new Error(error.message || 'Registration failed');
    }
  };

  const handleSaveInvoice = async (formData: CreateInvoiceData) => {
    try {
      const invoiceData: CreateInvoiceData = {
        ...formData,
        items: formData.items.map(item => ({
          description: item.description,
          quantity: item.quantity,
          price: item.price,
        })),
      };

      const newInvoice = await apiService.createInvoice(invoiceData);
      setInvoices(prev => [newInvoice, ...prev]);

      Alert.alert('Success', 'Invoice created successfully!');
      setCurrentScreen('invoices');

      return newInvoice; // Return the created invoice
    } catch (error: any) {
      throw new Error(error.message || 'Failed to create invoice');
    }
  };

  const handleUpdateInvoice = async (invoiceId: number, formData: {
    client: string;
    invoiceNumber: string;
    currency: string;
    date: string;
    dueDate: string;
    status: string;
    paidAmount: number;
    items: Array<{
      id?: number;
      description: string;
      quantity: number;
      price: number;
      amount: number;
    }>;
    notes: string;
    attachment_filename?: string | null;
  }) => {
    try {
      const totalAmount = formData.items.reduce((sum, item) => sum + item.amount, 0);
      
      logger.debug('Processing invoice update in handleUpdateInvoice', {
        invoiceId,
        client: formData.client
      });
      
      const clientId = parseInt(formData.client);
      if (isNaN(clientId)) {
        throw new Error(`Invalid client ID: ${formData.client}`);
      }
      
      const invoiceData: UpdateInvoiceData = {
        client_id: clientId,
        amount: totalAmount,
        currency: formData.currency,
        date: formData.date,
        due_date: formData.dueDate,
        status: formData.status as any,
        notes: formData.notes,
        items: formData.items.map(item => ({
          id: item.id,
          description: item.description,
          quantity: item.quantity,
          price: item.price,
        })),
      };

      // Include attachment_filename if it's present (for deletion)
      if (formData.attachment_filename !== undefined) {
        invoiceData.attachment_filename = formData.attachment_filename;
      }
      
      const updatedInvoice = await apiService.updateInvoice(invoiceId, invoiceData);
      setInvoices(prev => prev.map(invoice =>
        invoice.id === invoiceId ? updatedInvoice : invoice
      ));

      // Stay on the edit screen to see the updated data
      Alert.alert('Success', 'Invoice updated successfully!');
    } catch (error: any) {
      console.error('App: Update error:', error);
      throw new Error(error.message || 'Failed to update invoice');
    }
  };

  const handleUpdateExpense = async (expenseId: number, formData: Partial<Expense>) => {
    try {
      logger.debug('Updating expense', { expenseId, formData });
      const updatedExpense = await apiService.updateExpense(expenseId, formData);

      // Update the expense in the local state (if needed for the list)
      // For now, we'll just navigate back since the expense list will refresh

      Alert.alert('Success', 'Expense updated successfully!');
      setSelectedExpense(null);
      setCurrentScreen('expenses');
    } catch (error: any) {
      console.error('App: Update expense error:', error);
      throw new Error(error.message || 'Failed to update expense');
    }
  };

  const renderScreen = () => {
    switch (currentScreen) {
      case 'login':
        return (
          <LoginScreen
            onLogin={handleLogin}
            onNavigateToSignup={handleNavigateToSignup}
            onNavigateToForgotPassword={handleNavigateToForgotPassword}
          />
        );
      case 'signup':
        return (
          <SignupScreen
            onSignup={handleSignup}
            onNavigateToLogin={handleNavigateToLogin}
          />
        );
      case 'forgotPassword':
        return (
          <ForgotPasswordScreen
            onNavigateToLogin={handleNavigateToLogin}
          />
        );
      case 'resetPassword':
        return (
          <ResetPasswordScreen
            token={resetToken}
            onNavigateToLogin={handleNavigateToLogin}
          />
        );
      case 'dashboard':
        return (
          <DashboardScreen
            onNavigateToInvoices={handleNavigateToInvoices}
            onNavigateToClients={handleNavigateToClients}
            onNavigateToPayments={handleNavigateToPayments}
            onNavigateToExpenses={handleNavigateToExpenses}
            onNavigateToStatements={handleNavigateToStatements}
            onNavigateToAnalytics={handleNavigateToAnalytics}
            onNavigateToSettings={handleNavigateToSettings}
            onSignOut={handleSignOut}
            user={user || undefined}
          />
        );
      case 'invoices':
        return (
          <InvoicesScreen
            invoices={invoices}
            onNavigateToNewInvoice={handleNavigateToNewInvoice}
            onNavigateToEditInvoice={handleNavigateToEditInvoice}
            onNavigateBack={handleNavigateBack}
          />
        );
      case 'newInvoice':
        return (
          <NewInvoiceScreen
            clients={clients}
            onSaveInvoice={handleSaveInvoice}
            onNavigateBack={handleNavigateBackFromInvoice}
          />
        );
      case 'clients':
        return (
          <ClientsScreen
            clients={clients}
            onNavigateBack={handleNavigateBack}
            onNavigateToNewClient={handleNavigateToNewClient}
            onNavigateToEditClient={handleNavigateToEditClient}
            onClientAdded={handleClientAdded}
            onClientUpdated={handleClientUpdated}
            onClientDeleted={handleClientDeleted}
          />
        );
      case 'newClient':
        return (
          <NewClientScreen
            onNavigateBack={handleNavigateBackFromNewClient}
            onClientAdded={handleClientAdded}
          />
        );
      case 'editClient':
        if (!selectedClient) {
          setCurrentScreen('clients');
          return null;
        }
        return (
          <EditClientScreen
            client={selectedClient}
            onNavigateBack={handleNavigateBackFromEditClient}
            onClientUpdated={handleClientUpdated}
            onClientDeleted={handleClientDeleted}
          />
        );
      case 'editInvoice':
        if (!selectedInvoice) {
          setCurrentScreen('invoices');
          return null;
        }
        const invoiceToEdit = invoices.find(inv => inv.id === selectedInvoice);
        if (!invoiceToEdit) {
          setCurrentScreen('invoices');
          return null;
        }
        return (
          <EditInvoiceScreen
            invoice={invoiceToEdit}
            clients={clients}
            onUpdateInvoice={handleUpdateInvoice}
            onNavigateBack={handleNavigateBackFromEditInvoice}
          />
        );
      case 'payments':
        return (
          <PaymentsScreen
            onNavigateBack={handleNavigateBack}
          />
        );
      case 'expenses':
        return (
          <ExpensesScreen
            onNavigateBack={handleNavigateBack}
            onNavigateToNewExpense={handleNavigateToNewExpense}
            onNavigateToEditExpense={handleNavigateToEditExpense}
          />
        );
      case 'newExpense':
        return (
          <NewExpenseScreen
            onNavigateBack={handleNavigateBack}
            onExpenseCreated={async (expense: Expense) => {
              logger.info('Expense created', expense);
              setCurrentScreen('expenses');
              await loadData(); // Refresh data if needed
            }}
          />
        );
      case 'editExpense':
        return (
          selectedExpense ? (
            <EditExpenseScreen
              expense={selectedExpense}
              onUpdateExpense={handleUpdateExpense}
              onNavigateBack={() => {
                setSelectedExpense(null);
                setCurrentScreen('expenses');
              }}
            />
          ) : (
            <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
              <Text>No expense selected</Text>
            </View>
          )
        );
      case 'statements':
        return (
          <StatementsScreen
            onNavigateBack={handleNavigateBack}
            onNavigateToStatement={(statement: BankStatement) => {
              // Add statement detail navigation later
              logger.debug('Open statement', statement);
            }}
          />
        );
      case 'analytics':
        return (
          <AnalyticsScreen
            onNavigateBack={handleNavigateBack}
          />
        );
      case 'settings':
        return (
          <SettingsScreen
            onNavigateBack={handleNavigateBack}
            onNavigateToUsers={handleNavigateToUsers}
            onSignOut={handleSignOut}
          />
        );
      case 'users':
        return (
          <UsersScreen
            onNavigateBack={handleNavigateBack}
          />
        );
      default:
        return (
          <LoginScreen
            onLogin={handleLogin}
            onNavigateToSignup={handleNavigateToSignup}
            onNavigateToForgotPassword={handleNavigateToForgotPassword}
          />
        );
    }
  };

  if (loading) {
    return (
      <View style={styles.container}>
        <StatusBar style="auto" />
        <View style={styles.loadingContainer}>
          <Text style={styles.loadingText}>Loading...</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="auto" />
      {renderScreen()}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    fontSize: 18,
    color: '#666',
  },
});

export default App;