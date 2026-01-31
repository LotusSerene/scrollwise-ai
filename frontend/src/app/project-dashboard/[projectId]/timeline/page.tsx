"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  MapPin,
  Calendar,
  Link2,
  Map,
  Loader2,
  PlusCircle,
  Trash2,
  Pencil,
  Workflow,
  Map as MapPinIcon,
} from "lucide-react";
import { fetchApi } from "@/lib/api";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AddEventForm } from "@/components/AddEventForm";
import { EditEventForm } from "@/components/EditEventForm";
import { AddEventConnectionForm } from "@/components/AddEventConnectionForm";
import { EditEventConnectionForm } from "@/components/EditEventConnectionForm";
import { AddLocationForm } from "@/components/AddLocationForm";
import { EditLocationForm } from "@/components/EditLocationForm";
import { AddLocationConnectionForm } from "@/components/AddLocationConnectionForm";
import { EditLocationConnectionForm } from "@/components/EditLocationConnectionForm";
import { toast } from "sonner";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { useAuth } from "@/components/MockAuthProvider";

interface Event {
  id: string;
  title: string;
  description: string;
  date: string;
  character_id?: string;
  location_id?: string;
}

interface EventConnection {
  id: string;
  event1_id: string;
  event2_id: string;
  event1_title?: string;
  event2_title?: string;
  connection_type: string;
  description: string;
  impact: string;
}

interface Location {
  id: string;
  name: string;
  description: string;
  coordinates?: string;
}

interface LocationConnection {
  id: string;
  location1_id: string;
  location2_id: string;
  location1_name?: string;
  location2_name?: string;
  connection_type: string;
  description: string;
  travel_route?: string;
  cultural_exchange?: string;
}

interface EventsTabProps {
  projectId: string;
  events: Event[];
  isLoading: boolean;
  error: string | null;
  onAddEvent: () => void;
  onEditEvent: (event: Event) => void;
  onDeleteEvent: (eventId: string) => void;
  onAnalyzeEvents: () => void;
  isAnalyzingEvents: boolean;
}

const EventsTab = ({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  projectId,
  events,
  isLoading,
  error,
  onAddEvent,
  onEditEvent,
  onDeleteEvent,
  onAnalyzeEvents,
  isAnalyzingEvents,
}: EventsTabProps) => {
  const [eventToDeleteId, setEventToDeleteId] = useState<string | null>(null);
  const [isDeleteAlertOpen, setIsDeleteAlertOpen] = useState(false);

  const handleDeleteClick = (eventId: string) => {
    setEventToDeleteId(eventId);
    setIsDeleteAlertOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!eventToDeleteId) return;
    onDeleteEvent(eventToDeleteId);
    setEventToDeleteId(null);
    setIsDeleteAlertOpen(false);
  };

  return (
    <div className="mt-4">
      <div className="flex justify-between items-center mb-4">
        {/* Apply theme styles */}
        <h3 className="text-lg font-semibold text-primary font-display">
          Events Management
        </h3>
        {/* Button inherits theme styles */}
        <div className="flex space-x-2">
          <Button
            size="sm"
            onClick={onAnalyzeEvents}
            disabled={isAnalyzingEvents}
          >
            {isAnalyzingEvents ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Workflow className="mr-2 h-4 w-4" />
            )}
            Analyze Chapters for Events
          </Button>
          <Button size="sm" onClick={onAddEvent}>
            <PlusCircle className="mr-2 h-4 w-4" /> Add New Event
          </Button>
        </div>
      </div>

      {/* Apply theme styles to loading/error/empty states */}
      {isLoading && (
        <div className="flex justify-center items-center p-8 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="ml-2">Loading events...</p>
        </div>
      )}
      {error && <p className="text-destructive text-center">{error}</p>}
      {!isLoading && !error && events.length === 0 && (
        <p className="text-muted-foreground text-center italic">
          No events found for this project yet.
        </p>
      )}
      {!isLoading && !error && events.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {events.map((event) => (
            // Apply theme styles to Card
            <Card
              key={event.id}
              className="bg-card border border-border text-card-foreground flex flex-col justify-between rounded-lg"
            >
              <div>
                <CardHeader>
                  {/* Apply theme styles */}
                  <CardTitle className="text-lg text-foreground font-display">
                    {event.title}
                  </CardTitle>
                  <CardDescription className="text-muted-foreground">
                    {new Date(event.date).toLocaleDateString()}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {/* Apply theme styles */}
                  <p className="text-sm text-muted-foreground mb-3 line-clamp-3 h-[60px] overflow-hidden">
                    {event.description}
                  </p>
                </CardContent>
              </div>
              {/* Apply theme styles to footer and buttons */}
              <div className="flex justify-end space-x-2 p-4 border-t border-border/50">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEditEvent(event)}
                >
                  <Pencil className="h-4 w-4 mr-1" /> Edit
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDeleteClick(event.id)}
                >
                  <Trash2 className="h-4 w-4 mr-1" /> Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Apply theme styles to AlertDialog */}
      <AlertDialog open={isDeleteAlertOpen} onOpenChange={setIsDeleteAlertOpen}>
        <AlertDialogContent className="bg-card border-border text-card-foreground rounded-lg">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-destructive font-display">
              Are you absolutely sure?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              This action cannot be undone. This will permanently delete the
              event.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeleteConfirm}
            >
              Continue
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

interface EventConnectionsTabProps {
  projectId: string;
  events: Event[];
  connections: EventConnection[];
  isLoading: boolean;
  error: string | null;
  onAddConnection: () => void;
  onEditConnection: (connection: EventConnection) => void;
  onDeleteConnection: (connectionId: string) => void;
  onAnalyzeConnections: () => void;
  isAnalyzingConnections: boolean;
}

const EventConnectionsTab = ({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  projectId,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  events,
  connections,
  isLoading,
  error,
  onAddConnection,
  onEditConnection,
  onDeleteConnection,
  onAnalyzeConnections,
  isAnalyzingConnections,
}: EventConnectionsTabProps) => {
  const [connectionToDeleteId, setConnectionToDeleteId] = useState<
    string | null
  >(null);
  const [isDeleteConnAlertOpen, setIsDeleteConnAlertOpen] = useState(false);

  const handleDeleteConnClick = (connectionId: string) => {
    setConnectionToDeleteId(connectionId);
    setIsDeleteConnAlertOpen(true);
  };

  const handleDeleteConnConfirm = () => {
    if (!connectionToDeleteId) return;
    onDeleteConnection(connectionToDeleteId);
    setConnectionToDeleteId(null);
    setIsDeleteConnAlertOpen(false);
  };

  return (
    <div className="mt-4">
      <div className="flex justify-between items-center mb-4">
        {/* Apply theme styles */}
        <h3 className="text-lg font-semibold text-primary font-display">
          Event Connections
        </h3>
        {/* Button inherits theme styles */}
        <div className="flex space-x-2">
          <Button
            size="sm"
            onClick={onAnalyzeConnections}
            disabled={isAnalyzingConnections}
          >
            {isAnalyzingConnections ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Workflow className="mr-2 h-4 w-4" />
            )}
            Analyze Event Connections
          </Button>
          <Button size="sm" onClick={onAddConnection}>
            <PlusCircle className="mr-2 h-4 w-4" /> Add New Connection
          </Button>
        </div>
      </div>

      {/* Apply theme styles to loading/error/empty states */}
      {isLoading && (
        <div className="flex justify-center items-center p-8 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="ml-2">Loading connections...</p>
        </div>
      )}
      {error && <p className="text-destructive text-center">{error}</p>}
      {!isLoading && !error && connections.length === 0 && (
        <p className="text-muted-foreground text-center italic">
          No event connections found for this project yet.
        </p>
      )}

      {!isLoading && !error && connections.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {connections.map((conn) => (
            // Apply theme styles to Card
            <Card
              key={conn.id}
              className="bg-card border border-border text-card-foreground flex flex-col justify-between rounded-lg"
            >
              <div>
                <CardHeader>
                  {/* Apply theme styles */}
                  <CardTitle className="text-base text-foreground flex items-center flex-wrap font-display">
                    <Workflow className="h-5 w-5 mr-2 flex-shrink-0 text-primary" />
                    <span className="font-medium">
                      {conn.event1_title ??
                        `Event ${conn.event1_id.substring(0, 6)}`}
                    </span>
                    <Link2 className="h-4 w-4 mx-2 flex-shrink-0 text-muted-foreground" />
                    <span className="font-medium">
                      {conn.event2_title ??
                        `Event ${conn.event2_id.substring(0, 6)}`}
                    </span>
                  </CardTitle>
                  <CardDescription className="text-primary/80 pt-1 text-xs uppercase tracking-wider">
                    {conn.connection_type}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {/* Apply theme styles */}
                  <p className="text-sm text-foreground mb-1 font-medium">
                    Description:
                  </p>
                  <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                    {conn.description}
                  </p>
                  <p className="text-sm text-foreground mb-1 font-medium">
                    Impact:
                  </p>
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {conn.impact}
                  </p>
                </CardContent>
              </div>
              {/* Apply theme styles to footer and buttons */}
              <div className="flex justify-end space-x-2 p-4 border-t border-border/50">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEditConnection(conn)}
                >
                  <Pencil className="h-4 w-4 mr-1" /> Edit
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDeleteConnClick(conn.id)}
                >
                  <Trash2 className="h-4 w-4 mr-1" /> Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Apply theme styles to AlertDialog */}
      <AlertDialog
        open={isDeleteConnAlertOpen}
        onOpenChange={setIsDeleteConnAlertOpen}
      >
        <AlertDialogContent className="bg-card border-border text-card-foreground rounded-lg">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-destructive font-display">
              Are you absolutely sure?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              This action cannot be undone. This will permanently delete the
              event connection.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setIsDeleteConnAlertOpen(false)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeleteConnConfirm}
            >
              Continue
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

interface LocationsTabProps {
  projectId: string;
  locations: Location[];
  isLoading: boolean;
  error: string | null;
  onAddLocation: () => void;
  onEditLocation: (location: Location) => void;
  onDeleteLocation: (locationId: string) => void;
  onAnalyzeLocations: () => void;
  isAnalyzingLocations: boolean;
}

const LocationsTab = ({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  projectId,
  locations,
  isLoading,
  error,
  onAddLocation,
  onEditLocation,
  onDeleteLocation,
  onAnalyzeLocations,
  isAnalyzingLocations,
}: LocationsTabProps) => {
  const [locationToDeleteId, setLocationToDeleteId] = useState<string | null>(
    null
  );
  const [isDeleteLocAlertOpen, setIsDeleteLocAlertOpen] = useState(false);

  const handleDeleteLocClick = (locationId: string) => {
    setLocationToDeleteId(locationId);
    setIsDeleteLocAlertOpen(true);
  };

  const handleDeleteLocConfirm = () => {
    if (!locationToDeleteId) return;
    onDeleteLocation(locationToDeleteId);
    setLocationToDeleteId(null);
    setIsDeleteLocAlertOpen(false);
  };

  return (
    <div className="mt-4">
      <div className="flex justify-between items-center mb-4">
        {/* Apply theme styles */}
        <h3 className="text-lg font-semibold text-primary font-display">
          Locations Management
        </h3>
        {/* Button inherits theme styles */}
        <div className="flex space-x-2">
          <Button
            size="sm"
            onClick={onAnalyzeLocations}
            disabled={isAnalyzingLocations}
          >
            {isAnalyzingLocations ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Workflow className="mr-2 h-4 w-4" />
            )}
            Analyze Chapters for Locations
          </Button>
          <Button size="sm" onClick={onAddLocation}>
            <PlusCircle className="mr-2 h-4 w-4" /> Add New Location
          </Button>
        </div>
      </div>

      {/* Apply theme styles to loading/error/empty states */}
      {isLoading && (
        <div className="flex justify-center items-center p-8 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="ml-2">Loading locations...</p>
        </div>
      )}
      {error && <p className="text-destructive text-center">{error}</p>}
      {!isLoading && !error && locations.length === 0 && (
        <p className="text-muted-foreground text-center italic">
          No locations found for this project yet.
        </p>
      )}

      {!isLoading && !error && locations.length > 0 && (
        // Apply theme styles to Table container
        <div className="border border-border rounded-lg overflow-hidden">
          <Table>
            <TableBody>
              {locations.map((location) => (
                // Apply theme styles to TableRow
                <TableRow
                  key={location.id}
                  className="border-border hover:bg-accent/50"
                >
                  {/* Apply theme styles to TableCell */}
                  <TableCell className="font-medium flex items-center text-foreground">
                    <MapPinIcon className="h-4 w-4 mr-2 text-primary" />
                    {location.name}
                  </TableCell>
                  <TableCell className="font-medium flex items-center">
                    {location.coordinates && (
                      <CardDescription className="text-muted-foreground text-xs">
                        Coords: {location.coordinates}
                      </CardDescription>
                    )}
                  </TableCell>
                  {/* Apply theme styles to action buttons */}
                  <TableCell className="text-right">
                    <div className="flex justify-end space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onEditLocation(location)}
                      >
                        <Pencil className="h-4 w-4 mr-1" /> Edit
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeleteLocClick(location.id)}
                      >
                        <Trash2 className="h-4 w-4 mr-1" /> Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Apply theme styles to AlertDialog */}
      <AlertDialog
        open={isDeleteLocAlertOpen}
        onOpenChange={setIsDeleteLocAlertOpen}
      >
        <AlertDialogContent className="bg-card border-border text-card-foreground rounded-lg">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-destructive font-display">
              Are you absolutely sure?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              This action cannot be undone. This will permanently delete the
              location and potentially associated data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setIsDeleteLocAlertOpen(false)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeleteLocConfirm}
            >
              Continue
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

interface LocationConnectionsTabProps {
  projectId: string;
  locationConnections: LocationConnection[];
  isLoading: boolean;
  error: string | null;
  onAddLocationConnection: () => void;
  onEditLocationConnection: (connection: LocationConnection) => void;
  onDeleteLocationConnection: (connectionId: string) => void;
  onAnalyzeLocationConnections: () => void;
  isAnalyzingLocationConnections: boolean;
}

const LocationConnectionsTab = ({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  projectId,
  locationConnections,
  isLoading,
  error,
  onAddLocationConnection,
  onEditLocationConnection,
  onDeleteLocationConnection,
  onAnalyzeLocationConnections,
  isAnalyzingLocationConnections,
}: LocationConnectionsTabProps) => {
  const [locConnToDeleteId, setLocConnToDeleteId] = useState<string | null>(
    null
  );
  const [isDeleteLocConnAlertOpen, setIsDeleteLocConnAlertOpen] =
    useState(false);

  const handleDeleteLocConnClick = (connectionId: string) => {
    setLocConnToDeleteId(connectionId);
    setIsDeleteLocConnAlertOpen(true);
  };

  const handleDeleteLocConnConfirm = () => {
    if (!locConnToDeleteId) return;
    onDeleteLocationConnection(locConnToDeleteId);
    setLocConnToDeleteId(null);
    setIsDeleteLocConnAlertOpen(false);
  };

  return (
    <div className="mt-4">
      <div className="flex justify-between items-center mb-4">
        {/* Apply theme styles */}
        <h3 className="text-lg font-semibold text-primary font-display">
          Location Connections
        </h3>
        {/* Button inherits theme styles */}
        <div className="flex space-x-2">
          <Button
            size="sm"
            onClick={onAnalyzeLocationConnections}
            disabled={isAnalyzingLocationConnections}
          >
            {isAnalyzingLocationConnections ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Workflow className="mr-2 h-4 w-4" />
            )}
            Analyze Location Connections
          </Button>
          <Button size="sm" onClick={onAddLocationConnection}>
            <PlusCircle className="mr-2 h-4 w-4" /> Add New Connection
          </Button>
        </div>
      </div>

      {/* Apply theme styles to loading/error/empty states */}
      {isLoading && (
        <div className="flex justify-center items-center p-8 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="ml-2">Loading location connections...</p>
        </div>
      )}
      {error && <p className="text-destructive text-center">{error}</p>}
      {!isLoading && !error && locationConnections.length === 0 && (
        <p className="text-muted-foreground text-center italic">
          No location connections found for this project yet.
        </p>
      )}

      {!isLoading && !error && locationConnections.length > 0 && (
        // Apply theme styles to Table container
        <div className="border border-border rounded-lg overflow-hidden">
          <Table>
            <TableBody>
              {locationConnections.map((conn) => (
                // Apply theme styles to TableRow
                <TableRow
                  key={conn.id}
                  className="border-border hover:bg-accent/50"
                >
                  {/* Apply theme styles to TableCell */}
                  <TableCell className="font-medium flex items-center text-foreground">
                    <MapPinIcon className="h-4 w-4 mr-2 text-primary" />
                    {conn.location1_name}
                  </TableCell>
                  <TableCell className="font-medium flex items-center text-foreground">
                    <MapPinIcon className="h-4 w-4 mr-2 text-primary" />
                    {conn.location2_name}
                  </TableCell>
                  <TableCell>
                    <p className="text-sm text-foreground mb-1 font-medium">
                      Description:
                    </p>
                    <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                      {conn.description}
                    </p>
                    {conn.travel_route && (
                      <>
                        <p className="text-sm text-foreground mb-1 font-medium">
                          Travel Route:
                        </p>
                        <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                          {conn.travel_route}
                        </p>
                      </>
                    )}
                    {conn.cultural_exchange && (
                      <>
                        <p className="text-sm text-foreground mb-1 font-medium">
                          Cultural Exchange:
                        </p>
                        <p className="text-sm text-muted-foreground line-clamp-2">
                          {conn.cultural_exchange}
                        </p>
                      </>
                    )}
                  </TableCell>
                  {/* Apply theme styles to action buttons */}
                  <TableCell className="text-right">
                    <div className="flex justify-end space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onEditLocationConnection(conn)}
                      >
                        <Pencil className="h-4 w-4 mr-1" /> Edit
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeleteLocConnClick(conn.id)}
                      >
                        <Trash2 className="h-4 w-4 mr-1" /> Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Apply theme styles to AlertDialog */}
      <AlertDialog
        open={isDeleteLocConnAlertOpen}
        onOpenChange={setIsDeleteLocConnAlertOpen}
      >
        <AlertDialogContent className="bg-card border-border text-card-foreground rounded-lg">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-destructive font-display">
              Are you absolutely sure?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              This action cannot be undone. This will permanently delete the
              location connection.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => setIsDeleteLocConnAlertOpen(false)}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeleteLocConnConfirm}
            >
              Continue
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default function TimelinePage() {
  const params = useParams();
  const projectId = params?.projectId as string;
  const auth = useAuth();
  const [events, setEvents] = useState<Event[]>([]);
  const [connections, setConnections] = useState<EventConnection[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(true);
  const [isLoadingConnections, setIsLoadingConnections] = useState(true);
  const [isLoadingLocations, setIsLoadingLocations] = useState(true);
  const [errorEvents, setErrorEvents] = useState<string | null>(null);
  const [errorConnections, setErrorConnections] = useState<string | null>(null);
  const [errorLocations, setErrorLocations] = useState<string | null>(null);

  const [locationConnections, setLocationConnections] = useState<
    LocationConnection[]
  >([]);
  const [isLoadingLocationConnections, setIsLoadingLocationConnections] =
    useState(true);
  const [errorLocationConnections, setErrorLocationConnections] = useState<
    string | null
  >(null);

  const [isAddEventModalOpen, setIsAddEventModalOpen] = useState(false);
  const [eventToEdit, setEventToEdit] = useState<Event | null>(null);
  const [isEditEventModalOpen, setIsEditEventModalOpen] = useState(false);
  const [isAddConnectionModalOpen, setIsAddConnectionModalOpen] =
    useState(false);
  const [connectionToEdit, setConnectionToEdit] =
    useState<EventConnection | null>(null);
  const [isEditConnectionModalOpen, setIsEditConnectionModalOpen] =
    useState(false);

  const [isAddLocationModalOpen, setIsAddLocationModalOpen] = useState(false);
  const [locationToEdit, setLocationToEdit] = useState<Location | null>(null);
  const [isEditLocationModalOpen, setIsEditLocationModalOpen] = useState(false);

  const [
    isAddLocationConnectionModalOpen,
    setIsAddLocationConnectionModalOpen,
  ] = useState(false);
  const [locationConnectionToEdit, setLocationConnectionToEdit] =
    useState<LocationConnection | null>(null);
  const [
    isEditLocationConnectionModalOpen,
    setIsEditLocationConnectionModalOpen,
  ] = useState(false);

  const [isAnalyzingEvents, setIsAnalyzingEvents] = useState(false);
  const [isAnalyzingConnections, setIsAnalyzingConnections] = useState(false);
  const [isAnalyzingLocations, setIsAnalyzingLocations] = useState(false);
  const [isAnalyzingLocationConnections, setIsAnalyzingLocationConnections] =
    useState(false);

  const loadEvents = useCallback(
    async (token: string | undefined) => {
      if (!projectId) return;
      if (!token) {
        setErrorEvents("Authentication token is missing.");
        setIsLoadingEvents(false);
        return;
      }
      setIsLoadingEvents(true);
      setErrorEvents(null);
      // Token is passed as argument
      try {
        const data = await fetchApi<Event[]>(
          `/projects/${projectId}/events`,
          {},
          token
        );
        if (Array.isArray(data)) {
          data.sort(
            (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
          );
          setEvents(data);
        } else {
          console.warn(
            "loadEvents: API did not return an array. Received:",
            data
          );
          setEvents([]);
          setErrorEvents("Received unexpected data format for events.");
        }
      } catch (err) {
        console.error("Failed to fetch events:", err);
        setErrorEvents("Failed to load events.");
      } finally {
        setIsLoadingEvents(false);
      }
    },
    [projectId]
  ); // Keep projectId dependency

  const loadConnections = useCallback(
    async (token: string | undefined) => {
      if (!projectId) return;
      if (!token) {
        setErrorConnections("Authentication token is missing.");
        setIsLoadingConnections(false);
        return;
      }
      setIsLoadingConnections(true);
      setErrorConnections(null);
      // Token is passed as argument
      try {
        const data = await fetchApi<EventConnection[]>(
          `/projects/${projectId}/events/connections`,
          {},
          token
        );
        if (Array.isArray(data) && Array.isArray(events)) {
          const eventMap: Map<string, string> = new globalThis.Map(
            events.map((e) => [e.id, e.title])
          );
          const connectionsWithTitles = data.map((conn) => ({
            ...conn,
            event1_title:
              eventMap.get(conn.event1_id) ??
              `Event ${conn.event1_id.substring(0, 6)}`,
            event2_title:
              eventMap.get(conn.event2_id) ??
              `Event ${conn.event2_id.substring(0, 6)}`,
          }));
          setConnections(connectionsWithTitles);
        } else {
          console.warn(
            "loadConnections: API did not return an array or events state is not an array. Received data:",
            data,
            "Events:",
            events
          );
          setConnections([]);
          setErrorConnections(
            "Received unexpected data format for connections or missing event data."
          );
        }
      } catch (err) {
        console.error("Failed to fetch event connections:", err);
        setErrorConnections("Failed to load event connections.");
      } finally {
        setIsLoadingConnections(false);
      }
    },
    [projectId, events]
  ); // Keep dependencies

  const loadLocations = useCallback(
    async (token: string | undefined) => {
      if (!projectId) return;
      if (!token) {
        setErrorLocations("Authentication token is missing.");
        setIsLoadingLocations(false);
        return;
      }
      setIsLoadingLocations(true);
      setErrorLocations(null);
      // Token is passed as argument
      try {
        const data = await fetchApi<Location[]>(
          `/projects/${projectId}/locations`,
          {},
          token
        );
        if (Array.isArray(data)) {
          setLocations(data);
        } else {
          console.warn(
            "loadLocations: API did not return an array. Received:",
            data
          );
          setLocations([]);
          setErrorLocations("Received unexpected data format for locations.");
        }
      } catch (err) {
        console.error("Failed to fetch locations:", err);
        setErrorLocations("Failed to load locations.");
      } finally {
        setIsLoadingLocations(false);
      }
    },
    [projectId]
  ); // Keep projectId dependency

  const loadLocationConnections = useCallback(
    async (token: string | undefined) => {
      if (!projectId) return;
      if (!token) {
        setErrorLocationConnections("Authentication token is missing.");
        setIsLoadingLocationConnections(false);
        return;
      }
      setIsLoadingLocationConnections(true);
      setErrorLocationConnections(null);
      // Token is passed as argument
      try {
        // Fetch connections first
        const data = await fetchApi<LocationConnection[] | null>(
          `/projects/${projectId}/locations/connections`,
          {},
          token
        );
        console.log("loadLocationConnections: Received data from API:", data);

        // Ensure data is an array
        if (!Array.isArray(data)) {
          console.warn(
            "loadLocationConnections: API did not return an array. Received:",
            data
          );
          setLocationConnections([]);
          setErrorLocationConnections(
            "Received unexpected data format for location connections."
          );
          return; // Exit early
        }

        // Now check if locations are available for mapping names
        console.log(
          "loadLocationConnections: Current locations state for mapping:",
          locations
        );
        console.log(
          "loadLocationConnections: Is locations an array for mapping?",
          Array.isArray(locations)
        );

        let connectionsWithNames: LocationConnection[];

        if (Array.isArray(locations) && locations.length > 0) {
          // Locations are available, map names
          const locationMap: Map<string, string> = new globalThis.Map(
            locations.map((loc) => [loc.id, loc.name])
          );
          connectionsWithNames = data.map((conn) => ({
            ...conn,
            location1_name:
              locationMap.get(conn.location1_id) ?? // Use name from map or fallback
              `Loc ${conn.location1_id.substring(0, 6)}`,
            location2_name:
              locationMap.get(conn.location2_id) ?? // Use name from map or fallback
              `Loc ${conn.location2_id.substring(0, 6)}`,
          }));
          console.log("loadLocationConnections: Mapped names successfully.");
        } else {
          // Locations not available yet, map connections without names (using fallback)
          console.warn(
            "loadLocationConnections: Locations state not ready or empty. Mapping connections without names."
          );
          connectionsWithNames = data.map((conn) => ({
            ...conn,
            location1_name: `Loc ${conn.location1_id.substring(0, 6)}`, // Fallback only
            location2_name: `Loc ${conn.location2_id.substring(0, 6)}`, // Fallback only
          }));
        }

        console.log(
          "loadLocationConnections: Final connections state:",
          connectionsWithNames
        );
        setLocationConnections(connectionsWithNames);
      } catch (err) {
        console.error("Failed to fetch location connections:", err);
        setErrorLocationConnections("Failed to load location connections.");
      } finally {
        setIsLoadingLocationConnections(false);
      }
    },
    [projectId, locations]
  ); // Keep dependencies

  useEffect(() => {
    // Load events and locations first when authenticated
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      loadEvents(auth.user.id_token);
      loadLocations(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      setErrorEvents("Authentication required.");
      setErrorLocations("Authentication required.");
      setIsLoadingEvents(false);
      setIsLoadingLocations(false);
    }
    // Depend on auth state and projectId
  }, [
    projectId,
    auth.isLoading,
    auth.isAuthenticated,
    auth.user?.id_token,
    loadEvents,
    loadLocations,
  ]);

  // Load connections after events are loaded or loading finishes
  useEffect(() => {
    // Only run if events have been loaded and user is authenticated
    if (
      !isLoadingEvents &&
      projectId &&
      auth.isAuthenticated &&
      auth.user?.id_token
    ) {
      loadConnections(auth.user.id_token);
    }
    // Depend on events, loading state, auth state, and load function
  }, [
    events,
    isLoadingEvents,
    loadConnections,
    projectId,
    auth.isAuthenticated,
    auth.user?.id_token,
  ]);

  // Load location connections after locations are loaded or loading finishes
  useEffect(() => {
    // Only run if locations have been loaded and user is authenticated
    if (
      !isLoadingLocations &&
      projectId &&
      auth.isAuthenticated &&
      auth.user?.id_token
    ) {
      loadLocationConnections(auth.user.id_token);
    }
    // Depend on locations, loading state, auth state, and load function
  }, [
    locations,
    isLoadingLocations,
    loadLocationConnections,
    projectId,
    auth.isAuthenticated,
    auth.user?.id_token,
  ]);

  // Add check for projectId *after* hooks
  if (!projectId) {
    // Optionally return a loading indicator or an error message
    return <div>Loading project details...</div>;
  }

  const handleAddEvent = () => setIsAddEventModalOpen(true);
  const handleEditEvent = (event: Event) => {
    setEventToEdit(event);
    setIsEditEventModalOpen(true);
  };
  const handleDeleteEvent = async (eventId: string) => {
    const token = auth.user?.id_token;
    if (!token) {
      toast.error("Authentication required to delete event.");
      return;
    }
    try {
      await fetchApi(
        `/projects/${projectId}/events/${eventId}`,
        { method: "DELETE" },
        token
      );
      toast.success("Event deleted successfully.");
      setEvents((prev) => prev.filter((event) => event.id !== eventId));
    } catch (err) {
      console.error("Failed to delete event:", err);
      toast.error("Failed to delete event. Please try again.");
    }
  };
  const handleEventAdded = () => {
    setIsAddEventModalOpen(false);
    if (auth.isAuthenticated && auth.user?.id_token) {
      loadEvents(auth.user.id_token);
    }
  };
  const handleEventUpdated = () => {
    setIsEditEventModalOpen(false);
    setEventToEdit(null);
    if (auth.isAuthenticated && auth.user?.id_token) {
      loadEvents(auth.user.id_token);
    }
  };
  const handleCancelAddEvent = () => setIsAddEventModalOpen(false);
  const handleCancelEditEvent = () => {
    setIsEditEventModalOpen(false);
    setEventToEdit(null);
  };

  const handleAddConnection = () => setIsAddConnectionModalOpen(true);
  const handleConnectionAdded = () => {
    setIsAddConnectionModalOpen(false);
    if (auth.isAuthenticated && auth.user?.id_token) {
      loadConnections(auth.user.id_token);
    }
  };
  const handleCancelAddConnection = () => setIsAddConnectionModalOpen(false);

  const handleEditConnection = (connection: EventConnection) => {
    setConnectionToEdit(connection);
    setIsEditConnectionModalOpen(true);
  };

  const handleConnectionUpdated = () => {
    setIsEditConnectionModalOpen(false);
    setConnectionToEdit(null);
    if (auth.isAuthenticated && auth.user?.id_token) {
      loadConnections(auth.user.id_token);
    }
  };

  const handleCancelEditConnection = () => {
    setIsEditConnectionModalOpen(false);
    setConnectionToEdit(null);
  };

  const handleDeleteConnection = async (connectionId: string) => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to delete connection.");
      return;
    }
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi(
        `/projects/${projectId}/events/connections/${connectionId}`,
        { method: "DELETE" },
        token
      );
      toast.success("Connection deleted successfully.");
      setConnections((prev) => prev.filter((conn) => conn.id !== connectionId));
    } catch (err) {
      console.error("Failed to delete connection:", err);
      toast.error("Failed to delete connection. Please try again.");
    }
  };

  const handleAddLocation = () => setIsAddLocationModalOpen(true);

  const handleLocationAdded = () => {
    setIsAddLocationModalOpen(false);
    if (auth.isAuthenticated && auth.user?.id_token) {
      loadLocations(auth.user.id_token);
    }
  };

  const handleCancelAddLocation = () => setIsAddLocationModalOpen(false);

  const handleEditLocation = (location: Location) => {
    setLocationToEdit(location);
    setIsEditLocationModalOpen(true);
  };

  const handleLocationUpdated = () => {
    setIsEditLocationModalOpen(false);
    setLocationToEdit(null);
    if (auth.isAuthenticated && auth.user?.id_token) {
      loadLocations(auth.user.id_token);
    }
  };

  const handleCancelEditLocation = () => {
    setIsEditLocationModalOpen(false);
    setLocationToEdit(null);
  };

  const handleDeleteLocation = async (locationId: string) => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to delete location.");
      return;
    }
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi(
        `/projects/${projectId}/locations/${locationId}`,
        { method: "DELETE" },
        token
      );
      toast.success("Location deleted successfully.");
      setLocations((prev) => prev.filter((loc) => loc.id !== locationId));
      if (auth.isAuthenticated && auth.user?.id_token) {
        loadEvents(auth.user.id_token); // Reload events in case they were linked
      }
    } catch (err) {
      console.error("Failed to delete location:", err);
      toast.error("Failed to delete location. Please try again.");
    }
  };

  const handleAddLocationConnection = () =>
    setIsAddLocationConnectionModalOpen(true);

  const handleLocationConnectionAdded = () => {
    setIsAddLocationConnectionModalOpen(false);
    if (auth.isAuthenticated && auth.user?.id_token) {
      loadLocationConnections(auth.user.id_token);
    }
  };

  const handleCancelAddLocationConnection = () =>
    setIsAddLocationConnectionModalOpen(false);

  const handleEditLocationConnection = (connection: LocationConnection) => {
    setLocationConnectionToEdit(connection);
    setIsEditLocationConnectionModalOpen(true);
  };

  const handleLocationConnectionUpdated = () => {
    setIsEditLocationConnectionModalOpen(false);
    setLocationConnectionToEdit(null);
    if (auth.isAuthenticated && auth.user?.id_token) {
      loadLocationConnections(auth.user.id_token);
    }
  };

  const handleCancelEditLocationConnection = () => {
    setIsEditLocationConnectionModalOpen(false);
    setLocationConnectionToEdit(null);
  };

  const handleDeleteLocationConnection = async (connectionId: string) => {
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to delete location connection.");
      return;
    }
    const token = auth.user.id_token; // Get token
    try {
      await fetchApi(
        `/projects/${projectId}/locations/connections/${connectionId}`,
        { method: "DELETE" },
        token
      );
      toast.success("Location connection deleted successfully.");
      setLocationConnections((prev) =>
        prev.filter((conn) => conn.id !== connectionId)
      );
    } catch (err) {
      console.error("Failed to delete location connection:", err);
      toast.error("Failed to delete location connection. Please try again.");
    }
  };

  const handleAnalyzeChapterEvents = async () => {
    if (!projectId) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to analyze events.");
      return;
    }
    setIsAnalyzingEvents(true);
    const id = toast.loading("Analyzing chapters for events...");
    const token = auth.user.id_token; // Get token
    try {
      const result = await fetchApi<{ events: Event[] }>(
        `/projects/${projectId}/events/analyze-chapter`,
        { method: "POST" },
        token // Pass token
      );
      if (result && result.events) {
        toast.success(`Found ${result.events.length} new events.`, { id });
        loadEvents(token); // Re-fetch events to include new ones
      } else {
        toast.info("No new events found or analysis already complete.", { id });
      }
    } catch (error) {
      console.error("Error analyzing chapter events:", error);
      toast.error("Failed to analyze chapter events.", { id });
    } finally {
      setIsAnalyzingEvents(false);
    }
  };

  const handleAnalyzeEventConnections = async () => {
    if (!projectId) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to analyze event connections.");
      return;
    }
    setIsAnalyzingConnections(true);
    const id = toast.loading("Analyzing event connections...");
    const token = auth.user.id_token; // Get token
    try {
      const result = await fetchApi<{ event_connections: EventConnection[] }>(
        `/projects/${projectId}/events/analyze-connections`,
        { method: "POST" },
        token // Pass token
      );
      if (
        result &&
        result.event_connections &&
        result.event_connections.length > 0
      ) {
        toast.success(
          `Found ${result.event_connections.length} event connections.`,
          { id }
        );
        loadConnections(token); // Re-fetch connections
      } else {
        toast.info("No new event connections found.", { id });
      }
    } catch (error) {
      console.error("Error analyzing event connections:", error);
      toast.error("Failed to analyze event connections.", { id });
    } finally {
      setIsAnalyzingConnections(false);
    }
  };

  const handleAnalyzeChapterLocations = async () => {
    if (!projectId) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to analyze locations.");
      return;
    }
    setIsAnalyzingLocations(true);
    const id = toast.loading("Analyzing chapters for locations...");
    const token = auth.user.id_token; // Get token
    try {
      const result = await fetchApi<{ locations: Location[] }>(
        `/projects/${projectId}/locations/analyze-chapter`,
        { method: "POST" },
        token // Pass token
      );
      if (result && result.locations && result.locations.length > 0) {
        toast.success(`Found ${result.locations.length} new locations.`, {
          id,
        });
        loadLocations(token); // Re-fetch locations
      } else {
        toast.info("No new locations found or analysis already complete.", {
          id,
        });
      }
    } catch (error) {
      console.error("Error analyzing chapter locations:", error);
      toast.error("Failed to analyze chapter locations.", { id });
    } finally {
      setIsAnalyzingLocations(false);
    }
  };

  const handleAnalyzeLocationConnections = async () => {
    if (!projectId) return;
    if (!auth.isAuthenticated || !auth.user?.id_token) {
      toast.error("Authentication required to analyze location connections.");
      return;
    }
    setIsAnalyzingLocationConnections(true);
    const id = toast.loading("Analyzing location connections...");
    const token = auth.user.id_token; // Get token
    try {
      const result = await fetchApi<{
        location_connections: LocationConnection[];
      }>(
        `/projects/${projectId}/locations/analyze-connections`,
        { method: "POST" },
        token // Pass token
      );
      if (
        result &&
        result.location_connections &&
        result.location_connections.length > 0
      ) {
        toast.success(
          `Found ${result.location_connections.length} location connections.`,
          { id }
        );
        loadLocationConnections(token); // Re-fetch connections
      } else {
        toast.info("No new location connections found.", { id });
      }
    } catch (error) {
      console.error("Error analyzing location connections:", error);
      toast.error("Failed to analyze location connections.", { id });
    } finally {
      setIsAnalyzingLocationConnections(false);
    }
  };

  return (
    // Remove explicit text-white, rely on theme
    <section>
      <Tabs defaultValue="events" className="w-full">
        {/* Apply theme styles to TabsList and TabsTrigger */}
        <TabsList className="grid w-full grid-cols-4 bg-card border border-border rounded-lg">
          <TabsTrigger
            value="events"
            className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-md"
          >
            <Calendar className="h-4 w-4 mr-2" /> Events
          </TabsTrigger>
          <TabsTrigger
            value="event-connections"
            className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-md"
          >
            <Link2 className="h-4 w-4 mr-2" /> Event Connections
          </TabsTrigger>
          <TabsTrigger
            value="locations"
            className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-md"
          >
            <MapPin className="h-4 w-4 mr-2" /> Locations
          </TabsTrigger>
          <TabsTrigger
            value="location-connections"
            className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-md"
          >
            <Map className="h-4 w-4 mr-2" /> Location Connections
          </TabsTrigger>
        </TabsList>
        <TabsContent value="events">
          <EventsTab
            projectId={projectId}
            events={events}
            isLoading={isLoadingEvents}
            error={errorEvents}
            onAddEvent={handleAddEvent}
            onEditEvent={handleEditEvent}
            onDeleteEvent={handleDeleteEvent}
            onAnalyzeEvents={handleAnalyzeChapterEvents}
            isAnalyzingEvents={isAnalyzingEvents}
          />
        </TabsContent>
        <TabsContent value="event-connections">
          <EventConnectionsTab
            projectId={projectId}
            events={events}
            connections={connections}
            isLoading={isLoadingConnections}
            error={errorConnections}
            onAddConnection={handleAddConnection}
            onEditConnection={handleEditConnection}
            onDeleteConnection={handleDeleteConnection}
            onAnalyzeConnections={handleAnalyzeEventConnections}
            isAnalyzingConnections={isAnalyzingConnections}
          />
        </TabsContent>
        <TabsContent value="locations">
          <LocationsTab
            projectId={projectId}
            locations={locations}
            isLoading={isLoadingLocations}
            error={errorLocations}
            onAddLocation={handleAddLocation}
            onEditLocation={handleEditLocation}
            onDeleteLocation={handleDeleteLocation}
            onAnalyzeLocations={handleAnalyzeChapterLocations}
            isAnalyzingLocations={isAnalyzingLocations}
          />
        </TabsContent>
        <TabsContent value="location-connections">
          <LocationConnectionsTab
            projectId={projectId}
            locationConnections={locationConnections}
            isLoading={isLoadingLocationConnections}
            error={errorLocationConnections}
            onAddLocationConnection={handleAddLocationConnection}
            onEditLocationConnection={handleEditLocationConnection}
            onDeleteLocationConnection={handleDeleteLocationConnection}
            onAnalyzeLocationConnections={handleAnalyzeLocationConnections}
            isAnalyzingLocationConnections={isAnalyzingLocationConnections}
          />
        </TabsContent>
      </Tabs>

      {/* Apply theme styles to Dialogs */}
      <Dialog open={isAddEventModalOpen} onOpenChange={setIsAddEventModalOpen}>
        <DialogContent className="sm:max-w-[425px] bg-card border-border text-card-foreground rounded-lg">
          <DialogHeader>
            <DialogTitle className="text-primary font-display">
              Add New Event
            </DialogTitle>
          </DialogHeader>
          {/* Assuming AddEventForm uses themed components */}
          <AddEventForm
            projectId={projectId}
            onEventAdded={handleEventAdded}
            onCancel={handleCancelAddEvent}
            token={auth.user?.id_token || null}
          />
        </DialogContent>
      </Dialog>

      <Dialog
        open={isEditEventModalOpen}
        onOpenChange={setIsEditEventModalOpen}
      >
        <DialogContent className="sm:max-w-[425px] bg-card border-border text-card-foreground rounded-lg">
          <DialogHeader>
            <DialogTitle className="text-primary font-display">
              Edit Event
            </DialogTitle>
          </DialogHeader>
          {eventToEdit && (
            // Assuming EditEventForm uses themed components
            <EditEventForm
              projectId={projectId}
              event={eventToEdit}
              onEventUpdated={handleEventUpdated}
              onCancel={handleCancelEditEvent}
              token={auth.user?.id_token || null}
            />
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={isAddConnectionModalOpen}
        onOpenChange={setIsAddConnectionModalOpen}
      >
        <DialogContent className="sm:max-w-[480px] bg-card border-border text-card-foreground rounded-lg">
          <DialogHeader>
            <DialogTitle className="text-primary font-display">
              Add New Event Connection
            </DialogTitle>
          </DialogHeader>
          {/* Assuming AddEventConnectionForm uses themed components */}
          <AddEventConnectionForm
            projectId={projectId}
            events={events.map((e) => ({ id: e.id, title: e.title }))}
            onConnectionAdded={handleConnectionAdded}
            onCancel={handleCancelAddConnection}
            getAuthToken={() => auth.user?.id_token || null}
          />
        </DialogContent>
      </Dialog>

      <Dialog
        open={isEditConnectionModalOpen}
        onOpenChange={setIsEditConnectionModalOpen}
      >
        <DialogContent className="sm:max-w-[480px] bg-card border-border text-card-foreground rounded-lg">
          <DialogHeader>
            <DialogTitle className="text-primary font-display">
              Edit Event Connection
            </DialogTitle>
          </DialogHeader>
          {connectionToEdit && (
            // Assuming EditEventConnectionForm uses themed components
            <EditEventConnectionForm
              projectId={projectId}
              events={events.map((e) => ({ id: e.id, title: e.title }))}
              connection={connectionToEdit}
              onConnectionUpdated={handleConnectionUpdated}
              onCancel={handleCancelEditConnection}
              token={auth.user?.id_token || null}
            />
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={isAddLocationModalOpen}
        onOpenChange={setIsAddLocationModalOpen}
      >
        <DialogContent className="sm:max-w-[425px] bg-card border-border text-card-foreground rounded-lg">
          <DialogHeader>
            <DialogTitle className="text-primary font-display">
              Add New Location
            </DialogTitle>
          </DialogHeader>
          {/* Assuming AddLocationForm uses themed components */}
          <AddLocationForm
            projectId={projectId}
            onLocationAdded={handleLocationAdded}
            onCancel={handleCancelAddLocation}
            token={auth.user?.id_token || null}
          />
        </DialogContent>
      </Dialog>

      <Dialog
        open={isEditLocationModalOpen}
        onOpenChange={setIsEditLocationModalOpen}
      >
        <DialogContent className="sm:max-w-[425px] bg-card border-border text-card-foreground rounded-lg">
          <DialogHeader>
            <DialogTitle className="text-primary font-display">
              Edit Location
            </DialogTitle>
          </DialogHeader>
          {locationToEdit && (
            // Assuming EditLocationForm uses themed components
            <EditLocationForm
              projectId={projectId}
              location={locationToEdit}
              onLocationUpdated={handleLocationUpdated}
              onCancel={handleCancelEditLocation}
              token={auth.user?.id_token || null}
            />
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={isAddLocationConnectionModalOpen}
        onOpenChange={setIsAddLocationConnectionModalOpen}
      >
        <DialogContent className="sm:max-w-[480px] bg-card border-border text-card-foreground rounded-lg">
          <DialogHeader>
            <DialogTitle className="text-primary font-display">
              Add Location Connection
            </DialogTitle>
          </DialogHeader>
          {/* Assuming AddLocationConnectionForm uses themed components */}
          <AddLocationConnectionForm
            projectId={projectId}
            locations={locations.map((loc) => ({ id: loc.id, name: loc.name }))}
            onConnectionAdded={handleLocationConnectionAdded}
            onCancel={handleCancelAddLocationConnection}
            token={auth.user?.id_token || null}
          />
        </DialogContent>
      </Dialog>

      <Dialog
        open={isEditLocationConnectionModalOpen}
        onOpenChange={setIsEditLocationConnectionModalOpen}
      >
        <DialogContent className="sm:max-w-[480px] bg-card border-border text-card-foreground rounded-lg">
          <DialogHeader>
            <DialogTitle className="text-primary font-display">
              Edit Location Connection
            </DialogTitle>
          </DialogHeader>
          <>
            {locationConnectionToEdit && (
              // Assuming EditLocationConnectionForm uses themed components
              <EditLocationConnectionForm
                projectId={projectId}
                locations={locations.map((loc) => ({
                  id: loc.id,
                  name: loc.name,
                }))}
                connection={locationConnectionToEdit}
                onConnectionUpdated={handleLocationConnectionUpdated}
                onCancel={handleCancelEditLocationConnection}
                token={auth.user?.id_token || null}
              />
            )}
            {!locationConnectionToEdit && (
              <p className="text-gray-400 py-4">
                No location connection selected for editing.
              </p>
            )}
          </>
        </DialogContent>
      </Dialog>
    </section>
  );
}
