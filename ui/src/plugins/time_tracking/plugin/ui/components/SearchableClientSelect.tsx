import * as React from "react";
import { Check, ChevronsUpDown, Search, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { clientApi, Client } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

interface SearchableClientSelectProps {
  value?: number;
  onChange: (clientId: number) => void;
  placeholder?: string;
  className?: string;
}

export function SearchableClientSelect({
  value,
  onChange,
  placeholder = "Select client...",
  className,
}: SearchableClientSelectProps) {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");

  const { data: clientsData, isLoading } = useQuery({
    queryKey: ["clients-all"],
    queryFn: () => clientApi.getClients(0, 1000), // Get a large enough list for selection
  });

  const clients = clientsData?.items || [];
  const selectedClient = clients.find((client) => client.id === value);

  const filteredClients = clients.filter((client) =>
    client.name.toLowerCase().includes(search.toLowerCase()) ||
    (client.company || "").toLowerCase().includes(search.toLowerCase()) ||
    client.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            "w-full justify-between bg-background/50 border-border/50 h-10 px-3 rounded-xl font-normal text-sm",
            !selectedClient && "text-muted-foreground",
            className
          )}
        >
          <div className="flex items-center gap-2 truncate">
            <User className="h-4 w-4 shrink-0 opacity-50" />
            {selectedClient ? selectedClient.name : placeholder}
          </div>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0 p-1 bg-popover/90 backdrop-blur-md border-border/50 shadow-2xl rounded-xl" align="start">
        <div className="flex items-center border-b border-border/30 px-3 py-2">
          <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
          <input
            className="flex h-8 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
            placeholder="Search clients..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="max-h-[300px] overflow-y-auto p-1 custom-scrollbar">
          {isLoading ? (
            <div className="py-6 text-center text-sm text-muted-foreground animate-pulse">
              Loading clients...
            </div>
          ) : filteredClients.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No clients found.
            </div>
          ) : (
            <div className="space-y-1">
              {filteredClients.map((client) => (
                <button
                  key={client.id}
                  className={cn(
                    "relative flex w-full cursor-default select-none items-center rounded-lg py-2 px-3 text-sm outline-none transition-colors",
                    "hover:bg-primary/10 hover:text-primary",
                    value === client.id && "bg-primary/5 text-primary font-medium"
                  )}
                  onClick={() => {
                    onChange(client.id);
                    setOpen(false);
                    setSearch("");
                  }}
                >
                  <div className="flex flex-col items-start truncate overflow-hidden">
                    <span className="truncate w-full">{client.name}</span>
                    {client.company && (
                       <span className="text-[10px] opacity-60 truncate w-full">{client.company}</span>
                    )}
                  </div>
                  {value === client.id && (
                    <Check className="ml-auto h-4 w-4" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
