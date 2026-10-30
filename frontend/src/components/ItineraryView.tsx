
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  Divider,
  Link,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

import {
  AccessTime,
  CalendarMonth,
  DirectionsCar,
  ExpandMore,
  Explore,
  OpenInNew,
  Public,
} from "@mui/icons-material";

import type {
  GenerateTripResponse,
  ItineraryActivity,
  TripSource,
} from "../types/trip";

import TripMap from "./TripMap";

interface ItineraryViewProps {
  data: GenerateTripResponse;
}

const durationLabels: Record<string, string> = {
  short: "Short activity",
  half_day: "Half day",
  full_day: "Full day",
  unknown: "Duration unknown",
};

function getSourceDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "Source";
  }
}

function ActivitySources({
  activity,
  sources,
}: {
  activity: ItineraryActivity;
  sources: TripSource[];
}) {
  const relevantSources = activity.source_indices
    .map((index) => ({
      index,
      source: sources[index - 1],
    }))
    .filter(
      (item): item is { index: number; source: TripSource } =>
        item.source !== undefined
    );

  if (relevantSources.length === 0) {
    return null;
  }

  return (
    <Stack
    direction="row"
    sx={{ mt: 1.5, flexWrap: "wrap", gap: 1 }}
    >
      {relevantSources.map(({ index, source }) => (
        <Chip
          key={index}
          label={getSourceDomain(source.url)}
          size="small"
          variant="outlined"
          component="a"
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          clickable
          icon={<OpenInNew sx={{ fontSize: 14 }} />}
          sx={{
            maxWidth: "100%",
            borderRadius: 2,
            bgcolor: "grey.50",
            "& .MuiChip-label": {
              overflow: "hidden",
              textOverflow: "ellipsis",
            },
          }}
        />
      ))}
    </Stack>
  );
}


export default function ItineraryView({
  data,
}: ItineraryViewProps) {
  const { trip, sources } = data;

  return (
    <Box sx={{ mt: 5 }}>
      <Box sx={{ mb: 4 }}>
        <Typography
          variant="overline"
          sx={{
            color: "primary.main",
            fontWeight: 700,
            letterSpacing: 1.5,
          }}
        >
          Your personalized itinerary
        </Typography>

        <Typography
          variant="h4"
          sx={{ fontWeight: 800, mt: 1, mb: 2 }}
        >
          Discover {trip.destination}
        </Typography>

        <Chip
          icon={<CalendarMonth />}
          label={`${trip.days.length} days`}
          color="primary"
          variant="outlined"
        />
      </Box>

      <Stack spacing={3}>
        {trip.days.map((day) => (
          <Paper
            key={day.day}
            elevation={0}
            sx={{
              p: { xs: 2.5, sm: 4 },
              borderRadius: 4,
              border: "1px solid",
              borderColor: "divider",
              bgcolor: "background.paper",
            }}
          >
            <Stack
              direction="row"
              spacing={2}
              sx={{
                justifyContent: "space-between",
                alignItems: "center",
                mb: 2,
              }}
            >
              <Box>
                <Typography
                  variant="overline"
                  color="primary.main"
                  sx={{ fontWeight: 700 }}
                >
                  Day {String(day.day).padStart(2, "0")}
                </Typography>

                <Typography
                  variant="h6"
                  sx={{ fontWeight: 700 }}
                >
                  Your Adventures
                </Typography>
              </Box>

              <Explore color="primary" sx={{ fontSize: 32 }} />
            </Stack>

            {day.total_driving_duration_minutes != null && (
              <Stack
                direction="row"
                spacing={1}
                sx={{
                  alignItems: "center",
                  mb: 3,
                  px: 2,
                  py: 1.5,
                  bgcolor: "action.hover",
                  borderRadius: 2,
                }}
              >
                <DirectionsCar color="action" fontSize="small" />

                <Typography
                  variant="body2"
                  color="text.secondary"
                >
                  Estimated daily round-trip driving:{" "}
                  <Box
                    component="span"
                    sx={{ fontWeight: 700 }}
                  >
                    {day.total_driving_duration_minutes} min
                  </Box>
                </Typography>
              </Stack>
            )}

            <Stack spacing={3}>
              {day.activities.map((activity, index) => (
                <Box key={`${day.day}-${index}`}>
                  {index > 0 && <Divider sx={{ mb: 3 }} />}

                  <Stack
                    direction="row"
                    spacing={2}
                    sx={{ alignItems: "flex-start" }}
                  >
                    <Box
                      sx={{
                        width: 34,
                        height: 34,
                        flexShrink: 0,
                        borderRadius: "50%",
                        bgcolor: "primary.light",
                        color: "primary.contrastText",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: 700,
                      }}
                    >
                      {index + 1}
                    </Box>

                    <Box sx={{ minWidth: 0, flex: 1 }}>
                      <Typography
                        variant="subtitle1"
                        sx={{ fontWeight: 700, mb: 1 }}
                      >
                        {activity.name}
                      </Typography>

                      {activity.start_time &&
                        activity.end_time && (
                          <Stack
                            direction="row"
                            spacing={1}
                            sx={{
                              alignItems: "center",
                              mb: 1.5,
                              flexWrap: "wrap",
                              gap: 1,
                            }}
                          >
                            <Chip
                              icon={<AccessTime />}
                              label={`${activity.start_time} – ${activity.end_time}`}
                              size="small"
                              color="primary"
                              sx={{ fontWeight: 700 }}
                            />

                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Estimated schedule
                            </Typography>
                          </Stack>
                        )}

                      {index > 0 &&
                        activity.travel_minutes_from_previous !=
                          null && (
                          <Stack
                            direction="row"
                            spacing={1}
                            sx={{
                              alignItems: "center",
                              mb: 1.5,
                            }}
                          >
                            <DirectionsCar
                              sx={{
                                fontSize: 17,
                                color: "text.secondary",
                              }}
                            />

                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {
                                activity.travel_minutes_from_previous
                              }{" "}
                              min drive from previous stop
                            </Typography>
                          </Stack>
                        )}

                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ lineHeight: 1.8 }}
                      >
                        {activity.description}
                      </Typography>

                      <Stack
                        direction="row"
                        sx={{
                          mt: 2,
                          flexWrap: "wrap",
                          gap: 1,
                        }}
                      >
                        <Chip
                          label={activity.activity_type.replaceAll(
                            "_",
                            " "
                          )}
                          size="small"
                          color="primary"
                          variant="outlined"
                        />

                        <Chip
                          icon={<AccessTime />}
                          label={
                            durationLabels[
                              activity.duration_type
                            ] ?? "Duration unknown"
                          }
                          size="small"
                          variant="outlined"
                        />
                      </Stack>

                      <ActivitySources
                        activity={activity}
                        sources={sources}
                      />
                    </Box>
                  </Stack>
                </Box>
              ))}
            </Stack>
          </Paper>
        ))}
      </Stack>

      <TripMap trip={trip} />

      {sources.length > 0 && (
        <Accordion
          elevation={0}
          sx={{
            mt: 4,
            border: "1px solid",
            borderColor: "divider",
            borderRadius: "16px !important",
            "&:before": { display: "none" },
            overflow: "hidden",
          }}
        >
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Stack
              direction="row"
              spacing={1.5}
              sx={{ alignItems: "center" }}
            >
              <Public color="primary" />

              <Typography sx={{ fontWeight: 700 }}>
                Sources & References
              </Typography>

              <Chip
                label={sources.length}
                size="small"
                variant="outlined"
              />
            </Stack>
          </AccordionSummary>

          <AccordionDetails>
            <Divider sx={{ mb: 2 }} />

            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: {
                  xs: "1fr",
                  sm: "repeat(2, minmax(0, 1fr))",
                },
                gap: 1,
              }}
            >
              {sources.map((source, index) => (
                <Link
                  key={`${source.url}-${index}`}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  underline="none"
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    minWidth: 0,
                    p: 1.5,
                    borderRadius: 2,
                    bgcolor: "action.hover",
                    color: "text.primary",
                    "&:hover": {
                      bgcolor: "action.selected",
                    },
                  }}
                >
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: "block" }}
                    >
                      {getSourceDomain(source.url)}
                    </Typography>

                    <Typography
                      variant="body2"
                      noWrap
                      title={source.title}
                      sx={{ fontWeight: 500 }}
                    >
                      {source.title}
                    </Typography>
                  </Box>

                  <OpenInNew
                    sx={{
                      fontSize: 16,
                      color: "text.secondary",
                    }}
                  />
                </Link>
              ))}
            </Box>
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
}