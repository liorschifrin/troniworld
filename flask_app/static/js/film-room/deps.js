import React, {
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";

const html = htm.bind(React.createElement);

export { React, createRoot, html, useEffect, useMemo, useReducer, useRef, useState };
