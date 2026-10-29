
import { useEffect } from "react";

import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap,
} from "react-leaflet";

import { Box, Paper, Typography } from "@mui/material";

import L from "leaflet";
import "leaflet/dist/leaflet.css";

import type { Trip } from "../types/trip";

interface TripMapProps {
  trip: Trip;
}

interface MapAttraction {
  name: string;
  description: string;
  day: number;
  latitude: number;
  longitude: number;
}

const dayColors = [
  "#18796B",
  "#E89B50",
  "#5278C7",
  "#A064B8",
  "#D66A6A",
];

function createMarkerIcon(day: number): L.DivIcon {
  const color = dayColors[(day - 1) % dayColors.length];

  return L.divIcon({
    className: "",
    html: `
      <div style="
        width: 34px;
        height: 34px;
        background: ${color};
        color: white;
        border: 3px solid white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 13px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.2);
      ">
        ${day}
      </div>
    `,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

function FitMapBounds({
  attractions,
}: {
  attractions: MapAttraction[];
}) {
  const map = useMap();

  useEffect(() => {
    if (attractions.length === 0) return;

    if (attractions.length === 1) {
      map.setView(
        [attractions[0].latitude, attractions[0].longitude],
        12
      );
      return;
    }

    const bounds = L.latLngBounds(
      attractions.map((attraction) => [
        attraction.latitude,
        attraction.longitude,
      ])
    );

    map.fitBounds(bounds, {
      padding: [40, 40],
      maxZoom: 13,
    });
  }, [attractions, map]);

  return null;
}

export default function TripMap({ trip }: TripMapProps) {
  const attractions: MapAttraction[] = trip.days.flatMap(
    (day) =>
      day.activities
        .filter(
          (activity) =>
            activity.location_status === "verified" &&
            activity.latitude !== null &&
            activity.longitude !== null &&
            Number.isFinite(activity.latitude) &&
            Number.isFinite(activity.longitude)
        )
        .map((activity) => ({
          name: activity.name,
          description: activity.description,
          day: day.day,
          latitude: activity.latitude as number,
          longitude: activity.longitude as number,
        }))
  );

  if (attractions.length === 0) {
    return null;
  }

  return (
    <Paper
      elevation={0}
      sx={{
        mt: 4,
        p: { xs: 2, sm: 3 },
        borderRadius: 4,
        border: "1px solid",
        borderColor: "divider",
      }}
    >
      <Typography
        variant="h6"
        sx={{ fontWeight: 700, mb: 0.5 }}
      >
        Your Trip Map
      </Typography>

      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mb: 2 }}
      >
        Explore your attractions on the map.
        Marker numbers indicate the trip day.
      </Typography>

      <Box
        sx={{
          height: { xs: 350, sm: 450 },
          borderRadius: 3,
          overflow: "hidden",
          "& .leaflet-container": {
            width: "100%",
            height: "100%",
          },
        }}
      >
        <MapContainer
          center={[
            attractions[0].latitude,
            attractions[0].longitude,
          ]}
          zoom={11}
          scrollWheelZoom={false}
          style={{ width: "100%", height: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <FitMapBounds attractions={attractions} />

          {attractions.map((attraction, index) => (
            <Marker
              key={`${attraction.day}-${index}`}
              position={[
                attraction.latitude,
                attraction.longitude,
              ]}
              icon={createMarkerIcon(attraction.day)}
            >
              <Popup>
                <strong>
                  Day {attraction.day}: {attraction.name}
                </strong>

                <p>{attraction.description}</p>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </Box>
    </Paper>
  );
}