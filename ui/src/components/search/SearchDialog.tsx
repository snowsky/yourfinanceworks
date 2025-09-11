import { Command } from 'cmdk';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FileText, Users, CreditCard, Receipt, Building, Paperclip } from 'lucide-react';

import { useSearch } from './SearchProvider';
import { apiClient } from '@/lib/api';

interface SearchResult {
  id: string;
  type: string;
  title: string;
  subtitle: string;
  url: string;
  score: number;
  highlights: Record<string, string[]>;
}

interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  types_searched: string[];
}

const getEntityIcon = (type: string) => {
  switch (type) {
    case 'invoices': return FileText;
    case 'clients': return Users;
    case 'payments': return CreditCard;
    case 'expenses': return Receipt;
    case 'statements': return Building;
    case 'attachments': return Paperclip;
    default: return Search;
  }
};

const getEntityColor = (type: string) => {
  switch (type) {
    case 'invoices': return 'text-blue-600';
    case 'clients': return 'text-green-600';
    case 'payments': return 'text-purple-600';
    case 'expenses': return 'text-orange-600';
    case 'statements': return 'text-indigo-600';
    case 'attachments': return 'text-gray-600';
    default: return 'text-gray-500';
  }
};

export function SearchDialog() {
  const { isOpen, setIsOpen } = useSearch();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setIsOpen((open) => !open);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, [setIsOpen]);

  useEffect(() => {
    if (query.trim().length > 0) {
      const searchTimeout = setTimeout(async () => {
        setLoading(true);
        setError(null);
        try {
          const response = await apiClient.get<SearchResponse>(`/search?q=${encodeURIComponent(query)}&limit=20`);
          console.log('Search response:', response);
          console.log('Search results:', response.results);
          setResults(response.results);
        } catch (err) {
          console.error('Search error:', err);
          setError('Search failed. Please try again.');
          setResults([]);
        } finally {
          setLoading(false);
        }
      }, 300); // Debounce search

      return () => clearTimeout(searchTimeout);
    } else {
      setResults([]);
      setError(null);
    }
  }, [query]);

  const handleSelect = (result: SearchResult) => {
    if (result.url) {
      navigate(result.url);
      setIsOpen(false);
      setQuery('');
      setResults([]);
    }
  };

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    if (!open) {
      setQuery('');
      setResults([]);
      setError(null);
    }
  };

  return (
    <Command.Dialog 
      open={isOpen} 
      onOpenChange={handleOpenChange}
      className="fixed inset-0 z-50"
    >
      <div className="fixed inset-0 bg-black/50" />
      <div className="fixed left-1/2 top-1/2 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-2xl border">
        <Command className="rounded-lg">
          <div className="flex items-center border-b px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <Command.Input 
              value={query} 
              onValueChange={setQuery}
              placeholder="Search invoices, clients, payments, expenses..."
              className="flex h-12 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
            />
            {loading && (
              <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
            )}
          </div>
          
          <Command.List className="max-h-96 overflow-y-auto p-2">
            {query.trim().length === 0 && (
              <div className="py-6 text-center text-sm text-muted-foreground">
                <Search className="mx-auto h-8 w-8 mb-2 opacity-50" />
                <p>Type to search across all your data</p>
                <p className="text-xs mt-1">Use ⌘K (Mac) or Ctrl+K (Windows) to open search</p>
              </div>
            )}
            
            {error && (
              <div className="py-6 text-center text-sm text-red-600">
                <p>{error}</p>
              </div>
            )}
            
            {query.trim().length > 0 && !loading && results.length === 0 && !error && (
              <div className="py-6 text-center text-sm text-muted-foreground">
                <p>No results found for "{query}"</p>
                <p className="text-xs mt-1">Try different keywords or check spelling</p>
              </div>
            )}
            
            {results.map((result) => {
              const Icon = getEntityIcon(result.type);
              const colorClass = getEntityColor(result.type);
              
              return (
                <Command.Item 
                  key={`${result.type}-${result.id}`}
                  value={`${result.title} ${result.subtitle || ''}`}
                  onSelect={() => handleSelect(result)}
                  onClick={() => handleSelect(result)}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 aria-selected:bg-gray-100"
                >
                  <Icon className={`h-4 w-4 ${colorClass}`} />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{result.title}</div>
                    {result.subtitle && (
                      <div className="text-xs text-muted-foreground truncate">
                        {result.subtitle}
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground capitalize">
                    {result.type.replace('_', ' ')}
                  </div>
                </Command.Item>
              );
            })}
          </Command.List>
          
          {results.length > 0 && (
            <div className="border-t px-3 py-2 text-xs text-muted-foreground">
              Found {results.length} results • Press Enter to select • Esc to close
            </div>
          )}
        </Command>
      </div>
    </Command.Dialog>
  );
}
