import React, { useState, useEffect, useMemo } from "react";
import { Check, ChevronsUpDown, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Client } from "@/lib/api";

interface SmartClientSelectorProps {
  clients: Client[];
  value: string;
  onValueChange: (value: string) => void;
  onCreateNew: () => void;
  placeholder?: string;
  disabled?: boolean;
}

export function SmartClientSelector({
  clients,
  value,
  onValueChange,
  onCreateNew,
  placeholder = "Select a client...",
  disabled = false
}: SmartClientSelectorProps) {

  const [open, setOpen] = useState(false);

  const selectedClient = clients.find(client => client.id.toString() === value);

  // Smart suggestions based on recent activity, balance, etc.
  const sortedClients = useMemo(() => {
    return [...clients].sort((a, b) => {
      // Prioritize clients with outstanding balances
      if (a.balance > 0 && b.balance === 0) return -1;
      if (a.balance === 0 && b.balance > 0) return 1;
      
      // Then sort by name
      return a.name.localeCompare(b.name);
    });
  }, [clients]);

  // Categorize clients for better UX
  const recentClients = sortedClients.filter(client => client.balance > 0).slice(0, 3);
  const otherClients = sortedClients.filter(client => !recentClients.includes(client));
  


  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn("w-full justify-between", disabled && "opacity-50 cursor-not-allowed")}
          disabled={disabled}
        >
          {selectedClient ? (
            <div className="flex items-center space-x-2">
              <span>{selectedClient.name}</span>
              {selectedClient.balance > 0 && (
                <Badge variant="secondary" className="text-xs">
                  ${selectedClient.balance.toFixed(2)} due
                </Badge>
              )}
            </div>
          ) : (
            placeholder
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full p-0" align="start">
        <Command>
          <div className="flex items-center border-b px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <CommandInput
              placeholder="Search clients..."
              className="flex h-11 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
          <CommandList className="max-h-[300px] overflow-y-auto">
            {clients.length === 0 && (
              <CommandEmpty>
                <div className="py-6 text-center">
                  <p className="text-sm text-muted-foreground">No clients found</p>
                </div>
              </CommandEmpty>
            )}
            
            {recentClients.length > 0 && (
              <CommandGroup heading="Clients with Outstanding Balance">
                {recentClients.map((client) => (
                  <CommandItem
                    key={client.id}
                    value={`${client.name} ${client.email || ''} ${client.phone || ''}`.toLowerCase()}
                    onSelect={() => {
                      console.log('CommandItem onSelect called:', client.name, client.id);
                      onValueChange(client.id.toString());
                      setOpen(false);
                    }}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      console.log('CommandItem onClick called:', client.name, client.id);
                      onValueChange(client.id.toString());
                      setOpen(false);
                    }}
                    className="flex items-center justify-between cursor-pointer"
                  >
                    <div className="flex items-center space-x-2">
                      <Check
                        className={cn(
                          "h-4 w-4",
                          value === client.id.toString() ? "opacity-100" : "opacity-0"
                        )}
                      />
                      <div>
                        <p className="font-medium">{client.name}</p>
                        <p className="text-xs text-muted-foreground">{client.email}</p>
                      </div>
                    </div>
                    <Badge variant="destructive" className="text-xs">
                      ${client.balance.toFixed(2)}
                    </Badge>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            
            {otherClients.length > 0 && (
              <div className="p-1">
                <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                  {recentClients.length > 0 ? "Other Clients" : "All Clients"}
                </div>
                {otherClients.map((client) => (
                  <div
                    key={client.id}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onValueChange(client.id.toString());
                      setOpen(false);
                    }}
                    className="flex items-center space-x-2 cursor-pointer p-2 hover:bg-accent hover:text-accent-foreground rounded-sm"
                  >
                    <Check
                      className={cn(
                        "h-4 w-4",
                        value === client.id.toString() ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <div>
                      <p className="font-medium">{client.name}</p>
                      <p className="text-xs text-muted-foreground">{client.email}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            

          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}